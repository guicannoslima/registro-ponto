document.addEventListener('DOMContentLoaded', () => {
    const pagina = document.querySelector('[data-camera]');
    if (!pagina) return;
    const form = document.getElementById('camera-form');
    const video = document.getElementById('camera-video');
    const aviso = document.getElementById('camera-mensagem');
    const ligar = document.getElementById('camera-ligar');
    const capturar = document.getElementById('camera-capturar');
    const parar = document.getElementById('camera-parar');
    const desligada = document.getElementById('camera-desligada');
    const excluir = document.getElementById('camera-excluir');
    const pessoa = document.getElementById('camera-pessoa');
    const estado = document.getElementById('camera-cadastro-estado');
    const detalhe = document.getElementById('camera-cadastro-detalhe');
    const confirmacao = document.getElementById('camera-confirmacao');
    const fotoConfirmacao = document.getElementById('camera-confirmacao-foto');
    const genericaConfirmacao = document.getElementById('camera-confirmacao-generica');
    const automatico = pagina.dataset.modo !== 'cadastro';
    const terminal = pagina.dataset.modo === 'terminal';
    let stream = null;
    let ocupado = false;
    let abrindo = false;
    let geracao = 0;
    let timer = null;
    let cadastroAtual = null;
    let versaoConsulta = 0;
    let confirmando = false;
    let versaoConfirmacao = 0;
    let timerConfirmacao = null;

    const atualizarControles = () => {
        const consultado = !pessoa || (cadastroAtual && String(cadastroAtual.funcionario_id) === pessoa.value);
        if (capturar) {
            capturar.disabled = ocupado || !stream || !consultado;
            capturar.textContent = cadastroAtual?.cadastrado ? 'Substituir rosto' : 'Cadastrar rosto';
        }
        if (excluir) {
            excluir.hidden = !consultado || !cadastroAtual?.cadastrado;
            excluir.disabled = ocupado || !consultado;
        }
        if (pessoa) pessoa.disabled = ocupado;
    };
    const aplicarEstado = (dados) => {
        if (!pessoa || String(dados.funcionario_id) !== pessoa.value) return;
        cadastroAtual = dados;
        const opcao = pessoa.selectedOptions[0];
        opcao.textContent = `${opcao.dataset.nome} — ${dados.cadastrado ? 'Cadastrado' : 'Sem cadastro'}`;
        estado.textContent = dados.cadastrado ? 'Rosto cadastrado' : 'Rosto não cadastrado';
        estado.className = `selo selo--${dados.cadastrado ? 'sucesso' : 'atencao'}`;
        detalhe.textContent = dados.cadastrado
            ? `${opcao.dataset.nome}: você pode substituir o rosto ou remover o cadastro.`
            : `${opcao.dataset.nome}: use Cadastrar rosto para adicionar o cadastro facial.`;
        atualizarControles();
    };
    const consultarEstado = async () => {
        if (!pessoa) return;
        const versao = ++versaoConsulta;
        const selecionada = pessoa.value;
        cadastroAtual = null;
        estado.className = 'selo selo--neutro';
        estado.textContent = selecionada ? 'Consultando cadastro…' : 'Selecione um colaborador';
        detalhe.textContent = selecionada ? 'Aguarde a consulta do cadastro facial.' : 'O estado do cadastro facial será mostrado aqui.';
        atualizarControles();
        if (!selecionada) return;
        try {
            const url = new URL(window.location.href);
            url.searchParams.set('estado', '1');
            url.searchParams.set('funcionario', selecionada);
            const resposta = await fetch(url, { cache: 'no-store', headers: { Accept: 'application/json' } });
            if (!resposta.ok || !resposta.headers.get('content-type')?.includes('application/json')) throw new Error();
            const dados = await resposta.json();
            if (versao !== versaoConsulta || selecionada !== pessoa.value) return;
            aplicarEstado(dados);
        } catch {
            if (versao !== versaoConsulta || selecionada !== pessoa.value) return;
            estado.textContent = 'Cadastro não consultado';
            detalhe.textContent = 'Não foi possível consultar o cadastro. Selecione a pessoa novamente ou recarregue a página.';
        }
    };

    const mensagem = (texto, erro = false) => {
        if (aviso.textContent !== texto) aviso.textContent = texto;
        aviso.dataset.erro = String(erro);
    };
    const cancelarConfirmacao = () => {
        versaoConfirmacao += 1;
        clearTimeout(timerConfirmacao);
        confirmando = false;
        if (confirmacao) {
            confirmacao.hidden = true;
            fotoConfirmacao.removeAttribute('src');
        }
        aviso.hidden = false;
        ligar.disabled = ocupado || abrindo;
    };
    const mostrarConfirmacao = async (dados) => {
        if (!confirmacao || dados.repetido) return;
        const versao = ++versaoConfirmacao;
        confirmando = true;
        ligar.disabled = true;
        document.getElementById('camera-confirmacao-titulo').textContent = dados.mensagem;
        genericaConfirmacao.querySelector('.avatar-generico__nome').textContent = dados.confirmacao.nome;
        fotoConfirmacao.alt = `Foto de ${dados.confirmacao.nome}`;
        fotoConfirmacao.hidden = true;
        genericaConfirmacao.hidden = false;
        aviso.hidden = true;
        if (dados.confirmacao.foto_url) {
            fotoConfirmacao.src = dados.confirmacao.foto_url;
            const carregou = await Promise.race([
                fotoConfirmacao.decode().then(() => true).catch(() => false),
                new Promise((resolve) => setTimeout(() => resolve(false), 2000)),
            ]);
            if (versao !== versaoConfirmacao) return;
            fotoConfirmacao.hidden = !carregou;
            genericaConfirmacao.hidden = carregou;
        }
        if (versao !== versaoConfirmacao || document.hidden) return;
        confirmacao.hidden = false;
        timerConfirmacao = setTimeout(() => {
            cancelarConfirmacao();
            if (terminal) {
                mensagem('Aguardando próximo colaborador.');
                agendar(0);
            }
        }, Number(pagina.dataset.confirmacaoMs));
    };
    const desligar = () => {
        geracao += 1;
        clearTimeout(timer);
        cancelarConfirmacao();
        stream?.getTracks().forEach((track) => track.stop());
        stream = null;
        video.srcObject = null;
        video.hidden = true;
        desligada.hidden = false;
        parar.hidden = true;
        atualizarControles();
        ligar.hidden = false;
        ligar.disabled = ocupado || abrindo;
    };
    const agendar = (atraso = 3500) => {
        clearTimeout(timer);
        if (automatico && stream && !document.hidden && !confirmando) timer = setTimeout(processar, atraso);
    };
    const enviar = async (dados) => {
        const resposta = await fetch(window.location.href, {
            method: 'POST', body: dados, headers: { Accept: 'application/json' },
        });
        if (!resposta.headers.get('content-type')?.includes('application/json')) {
            throw new Error('Sua sessão terminou. Entre novamente para continuar.');
        }
        return { ok: resposta.ok, dados: await resposta.json() };
    };
    const processar = async () => {
        if (ocupado || !stream || document.hidden || confirmando) return;
        if (!video.videoWidth) { agendar(); return; }
        if (!automatico && !form.reportValidity()) return;
        if (pessoa && (!cadastroAtual || String(cadastroAtual.funcionario_id) !== pessoa.value)) return;
        if (cadastroAtual?.cadastrado
            && !window.confirm(`Substituir o rosto cadastrado de ${pessoa.selectedOptions[0].dataset.nome}?`)) return;
        const tentativa = geracao;
        const dados = new FormData(form);
        ocupado = true;
        atualizarControles();
        if (!automatico) mensagem('Processando o rosto. Aguarde a confirmação do cadastro.');
        try {
            const canvas = document.createElement('canvas');
            const escala = Math.min(1, 640 / video.videoWidth, 480 / video.videoHeight);
            canvas.width = Math.round(video.videoWidth * escala);
            canvas.height = Math.round(video.videoHeight * escala);
            canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
            const foto = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.9));
            if (tentativa !== geracao) return;
            if (!foto) throw new Error('A captura falhou. Tente novamente.');
            dados.append('foto', foto, 'camera.jpg');
            const resultado = await enviar(dados);
            if (resultado.ok && pessoa) aplicarEstado(resultado.dados);
            if (tentativa !== geracao) return;
            mensagem(resultado.dados.repetido ? 'Aguardando próximo colaborador.'
                : resultado.dados.mensagem || resultado.dados.erro, !resultado.ok);
            if (resultado.ok) {
                if (!terminal) desligar();
                if (automatico) await mostrarConfirmacao(resultado.dados);
            } else if (automatico && !resultado.dados.continuar) {
                desligar();
            }
        } catch (erro) {
            if (pessoa) consultarEstado();
            if (tentativa !== geracao) return;
            desligar();
            mensagem(erro instanceof TypeError
                ? (automatico ? 'A conexão falhou. Confira as batidas antes de retomar a câmera.'
                    : 'A conexão falhou. Confira o estado do cadastro antes de tentar novamente.')
                : erro.message || 'Não foi possível confirmar a operação. Confira as batidas antes de retomar.', true);
        } finally {
            ocupado = false;
            atualizarControles();
            ligar.disabled = abrindo || confirmando;
            if (tentativa === geracao) agendar();
        }
    };
    const abrir = async () => {
        if (abrindo || ocupado || stream || document.hidden || confirmando) return;
        if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
            mensagem('A câmera exige HTTPS ou localhost e um navegador compatível. Use o registro comum no painel.', true);
            ligar.hidden = false;
            return;
        }
        const tentativa = ++geracao;
        abrindo = true;
        ligar.hidden = true;
        mensagem('Abrindo câmera. Autorize o acesso no navegador quando solicitado.');
        try {
            const nova = await navigator.mediaDevices.getUserMedia({
                audio: false, video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
            });
            if (tentativa !== geracao) {
                nova.getTracks().forEach((track) => track.stop());
                return;
            }
            stream = nova;
            video.srcObject = stream;
            video.hidden = false;
            desligada.hidden = true;
            parar.hidden = false;
            await video.play();
            if (tentativa !== geracao) return;
            atualizarControles();
            mensagem(automatico ? 'Aguardando rosto. O ponto será registrado automaticamente.'
                : 'Confirme a pessoa selecionada e capture o rosto.');
            stream.getVideoTracks()[0].addEventListener('ended', () => {
                desligar();
                mensagem('A câmera foi desconectada. Reconecte ou use o registro comum.', true);
            });
            if (automatico) processar();
        } catch (erro) {
            if (tentativa !== geracao) return;
            desligar();
            const textos = {
                NotAllowedError: 'Acesso à câmera negado. Autorize no navegador ou use o registro comum.',
                NotFoundError: 'Nenhuma câmera encontrada neste computador. Use o registro comum no painel.',
                NotReadableError: 'Não foi possível acessar a câmera. Feche outras abas ou aplicativos que a usam, confira o bloqueio de privacidade e tente novamente.',
            };
            mensagem(textos[erro.name] || 'Não foi possível ligar a câmera. Tente novamente ou use o registro comum.', true);
        } finally {
            abrindo = false;
            ligar.disabled = ocupado;
        }
    };
    ligar.addEventListener('click', abrir);
    parar.addEventListener('click', () => { desligar(); mensagem('Câmera pausada. Use Retomar câmera para continuar.'); });
    form.addEventListener('submit', (evento) => {
        evento.preventDefault();
        if (!automatico) processar();
    });
    excluir?.addEventListener('click', async () => {
        if (ocupado || !cadastroAtual?.cadastrado || !form.reportValidity()) return;
        if (!window.confirm(`Remover o cadastro facial de ${pessoa.selectedOptions[0].textContent}?`)) return;
        const dados = new FormData(form);
        dados.append('acao', 'excluir');
        ocupado = true;
        atualizarControles();
        try {
            const resultado = await enviar(dados);
            if (resultado.ok) aplicarEstado(resultado.dados);
            mensagem(resultado.dados.mensagem || resultado.dados.erro, !resultado.ok);
        } catch (erro) {
            consultarEstado();
            mensagem(erro instanceof TypeError
                ? 'A remoção não pôde ser confirmada. Confira o estado do cadastro antes de tentar novamente.'
                : erro.message, true);
        }
        finally {
            ocupado = false;
            atualizarControles();
        }
    });
    pessoa?.addEventListener('change', consultarEstado);
    window.addEventListener('pagehide', desligar);
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) { desligar(); mensagem('Câmera pausada. Use Retomar câmera para continuar.'); }
    });
    consultarEstado();
    abrir();
});
