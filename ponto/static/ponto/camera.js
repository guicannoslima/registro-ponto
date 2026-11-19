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
    const automatico = pagina.dataset.modo !== 'cadastro';
    const terminal = pagina.dataset.modo === 'terminal';
    let stream = null;
    let ocupado = false;
    let abrindo = false;
    let geracao = 0;
    let timer = null;

    const mensagem = (texto, erro = false) => {
        if (aviso.textContent !== texto) aviso.textContent = texto;
        aviso.dataset.erro = String(erro);
    };
    const desligar = () => {
        geracao += 1;
        clearTimeout(timer);
        stream?.getTracks().forEach((track) => track.stop());
        stream = null;
        video.srcObject = null;
        video.hidden = true;
        desligada.hidden = false;
        parar.hidden = true;
        if (capturar) capturar.disabled = true;
        ligar.hidden = false;
        ligar.disabled = ocupado || abrindo;
    };
    const agendar = () => {
        clearTimeout(timer);
        if (automatico && stream && !document.hidden) timer = setTimeout(processar, 3500);
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
        if (ocupado || !stream || document.hidden) return;
        if (!video.videoWidth) { agendar(); return; }
        if (!automatico && !form.reportValidity()) return;
        const tentativa = geracao;
        ocupado = true;
        if (capturar) capturar.disabled = true;
        if (excluir) excluir.disabled = true;
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
            const dados = new FormData(form);
            dados.append('foto', foto, 'camera.jpg');
            const resultado = await enviar(dados);
            if (tentativa !== geracao) return;
            mensagem(resultado.dados.mensagem || resultado.dados.erro, !resultado.ok);
            if (resultado.ok) {
                if (!terminal) desligar();
            } else if (automatico && !resultado.dados.continuar) {
                desligar();
            }
        } catch (erro) {
            if (tentativa !== geracao) return;
            desligar();
            mensagem(erro instanceof TypeError
                ? 'A conexão falhou. Confira as batidas antes de retomar a câmera.'
                : erro.message || 'Não foi possível confirmar a operação. Confira as batidas antes de retomar.', true);
        } finally {
            ocupado = false;
            if (capturar) capturar.disabled = !stream;
            if (excluir) excluir.disabled = false;
            ligar.disabled = abrindo;
            if (tentativa === geracao) agendar();
        }
    };
    const abrir = async () => {
        if (abrindo || ocupado || stream || document.hidden) return;
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
            if (capturar) capturar.disabled = false;
            mensagem(automatico ? 'Aguardando rosto. O ponto será registrado automaticamente.'
                : 'Confirme a pessoa selecionada e pressione Cadastrar rosto.');
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
        if (ocupado || !form.reportValidity()) return;
        const pessoa = document.getElementById('camera-pessoa');
        if (!window.confirm(`Remover o cadastro facial de ${pessoa.selectedOptions[0].textContent}?`)) return;
        ocupado = true;
        excluir.disabled = true;
        if (capturar) capturar.disabled = true;
        try {
            const dados = new FormData(form);
            dados.append('acao', 'excluir');
            const resultado = await enviar(dados);
            mensagem(resultado.dados.mensagem || resultado.dados.erro, !resultado.ok);
        } catch (erro) { mensagem(erro.message, true); }
        finally {
            ocupado = false;
            excluir.disabled = false;
            if (capturar) capturar.disabled = !stream;
        }
    });
    window.addEventListener('pagehide', desligar);
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) { desligar(); mensagem('Câmera pausada. Use Retomar câmera para continuar.'); }
    });
    abrir();
});
