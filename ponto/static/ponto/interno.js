// Diálogo da aplicação: foco inicial no cancelamento; Escape cancela e devolve o foco.
window.confirmDialog = ({ titulo, mensagem, confirmar }) => {
    const dialog = document.getElementById('confirm-dialog');
    if (!dialog || dialog.open) return Promise.resolve(false);
    document.getElementById('confirm-dialog-titulo').textContent = titulo;
    document.getElementById('confirm-dialog-mensagem').textContent = mensagem;
    document.getElementById('confirm-dialog-confirmar').textContent = confirmar;
    dialog.returnValue = 'cancelar';
    return new Promise((resolve) => {
        dialog.addEventListener('close', () => resolve(dialog.returnValue === 'confirmar'), { once: true });
        dialog.showModal();
    });
};

// CPF: apresenta a máscara sem alterar o armazenamento numérico validado no servidor.
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-mascara="cpf"]').forEach((campo) => {
        const formatar = () => {
            const cursor = campo.selectionStart;
            const digitosAntes = campo.value.slice(0, cursor).replace(/\D/g, '').length;
            campo.value = campo.value.replace(/\D/g, '').slice(0, 11)
                .replace(/(\d{3})(\d)/, '$1.$2')
                .replace(/(\d{3})(\d)/, '$1.$2')
                .replace(/(\d{3})(\d)/, '$1-$2');
            let posicao = 0;
            let encontrados = 0;
            while (posicao < campo.value.length && encontrados < digitosAntes) {
                if (/\d/.test(campo.value[posicao])) encontrados += 1;
                posicao += 1;
            }
            if (document.activeElement === campo) campo.setSelectionRange(posicao, posicao);
        };
        campo.addEventListener('beforeinput', (evento) => {
            const inicio = campo.selectionStart;
            if (inicio !== campo.selectionEnd) return;
            if (evento.inputType === 'deleteContentBackward' && /[.\-]/.test(campo.value[inicio - 1] || '')) {
                campo.setSelectionRange(inicio - 2, inicio);
            } else if (evento.inputType === 'deleteContentForward' && /[.\-]/.test(campo.value[inicio] || '')) {
                campo.setSelectionRange(inicio, inicio + 2);
            }
        });
        campo.addEventListener('input', formatar);
        formatar();
    });
});

// Lançar ponto manual: atualiza o painel "batidas já registradas" ao trocar a pessoa ou a data.
document.addEventListener('DOMContentLoaded', () => {
    const painel = document.getElementById('batidas-do-dia');
    const funcionario = document.getElementById('id_funcionario');
    const dataHora = document.getElementById('id_data_hora');
    if (!painel || !funcionario || !dataHora) {
        return;
    }

    const atualizar = () => {
        if (!funcionario.value) {
            return;
        }
        // Sem data no formulário, mantém o último dia mostrado no painel (por exemplo, ao voltar de uma exclusão).
        const data = (dataHora.value || '').slice(0, 10) || painel.dataset.dia || painel.dataset.hoje;
        const parametros = new URLSearchParams({ parcial: '1', funcionario: funcionario.value, data });
        fetch(`${painel.dataset.url}?${parametros}`)
            .then((resposta) => (resposta.ok ? resposta.text() : Promise.reject(resposta.status)))
            .then((html) => {
                painel.innerHTML = html;
                painel.dataset.dia = data;
            })
            .catch(() => {
                // Sem o painel atualizado o formulário continua funcionando normalmente.
            });
    };

    funcionario.addEventListener('change', atualizar);
    dataHora.addEventListener('change', atualizar);
});

// Lançar folga: atualiza o efeito no banco de horas ao trocar pessoas, data ou tipo.
document.addEventListener('DOMContentLoaded', () => {
    const painel = document.getElementById('efeito-folga');
    const formulario = document.querySelector('[data-folga]');
    if (!painel || !formulario) {
        return;
    }

    const atualizar = () => {
        const parametros = new URLSearchParams({ parcial: '1' });
        new FormData(formulario).forEach((valor, nome) => {
            if (['funcionarios', 'data', 'tipo'].includes(nome)) {
                parametros.append(nome, valor);
            }
        });
        fetch(`${painel.dataset.url}?${parametros}`)
            .then((resposta) => (resposta.ok ? resposta.text() : Promise.reject(resposta.status)))
            .then((html) => {
                painel.innerHTML = html;
            })
            .catch(() => {
                // Sem o efeito atualizado o formulário continua funcionando normalmente.
            });
    };

    formulario.addEventListener('change', (evento) => {
        if (['funcionarios', 'data', 'tipo'].includes(evento.target.name)) {
            atualizar();
        }
    });
});

// Página inicial: troca de abas sem recarregar. Sem JS, cada aba é um link ?aba=… tratado pelo servidor.
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-abas]').forEach((grupo) => {
        const abas = Array.from(grupo.querySelectorAll('[role="tab"]'));

        const ativar = (aba, focar) => {
            abas.forEach((outra) => {
                const ativa = outra === aba;
                outra.setAttribute('aria-selected', String(ativa));
                outra.tabIndex = ativa ? 0 : -1;
                document.getElementById(outra.getAttribute('aria-controls')).hidden = !ativa;
            });
            if (focar) {
                aba.focus();
            }
            const url = new URL(window.location.href);
            url.searchParams.set('aba', aba.id.replace('aba-', ''));
            window.history.replaceState(null, '', url);
        };

        abas.forEach((aba, indice) => {
            aba.addEventListener('click', (evento) => {
                evento.preventDefault();
                ativar(aba, false);
            });
            aba.addEventListener('keydown', (evento) => {
                const passos = { ArrowRight: 1, ArrowLeft: -1 };
                if (evento.key in passos) {
                    evento.preventDefault();
                    ativar(abas[(indice + passos[evento.key] + abas.length) % abas.length], true);
                } else if (evento.key === 'Home' || evento.key === 'End') {
                    evento.preventDefault();
                    ativar(evento.key === 'Home' ? abas[0] : abas[abas.length - 1], true);
                }
            });
        });
    });
});

// Voltar ao topo: aparece depois de rolar 200px; ao clicar, sobe e devolve o foco para a logo do header.
document.addEventListener('DOMContentLoaded', () => {
    const botao = document.getElementById('voltar-topo');
    if (!botao) {
        return;
    }

    const atualizar = () => {
        botao.hidden = window.scrollY <= 200;
    };

    botao.addEventListener('click', () => {
        const reduzir = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        window.scrollTo({ top: 0, behavior: reduzir ? 'auto' : 'smooth' });
        document.querySelector('.logo-topo')?.focus({ preventScroll: true });
    });

    window.addEventListener('scroll', atualizar, { passive: true });
    window.addEventListener('resize', atualizar);
    atualizar();
});

// Menus por clique: um grupo aberto, fechamento por clique fora, foco fora ou Escape.
document.addEventListener('DOMContentLoaded', () => {
    const menu = document.querySelector('[data-menu]');
    if (!menu) return;
    const grupos = [...menu.querySelectorAll('details')];
    grupos.forEach((grupo) => {
        grupo.addEventListener('toggle', () => {
            if (grupo.open) grupos.forEach((outro) => { if (outro !== grupo) outro.open = false; });
        });
        grupo.addEventListener('keydown', (evento) => {
            if (evento.key === 'Escape') {
                grupo.open = false;
                grupo.querySelector('summary').focus();
            }
        });
        grupo.addEventListener('focusout', () => {
            setTimeout(() => { if (!grupo.contains(document.activeElement)) grupo.open = false; }, 0);
        });
    });
    document.addEventListener('click', (evento) => {
        grupos.forEach((grupo) => { if (!grupo.contains(evento.target)) grupo.open = false; });
    });
});

// Se o arquivo da foto não estiver disponível, mantém a imagem genérica com o nome.
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-foto-perfil]').forEach((foto) => {
        const usarGenerica = () => {
            foto.hidden = true;
            foto.parentElement.querySelector('[data-avatar-generico]').hidden = false;
        };
        foto.addEventListener('error', usarGenerica);
        if (foto.complete && !foto.naturalWidth) usarGenerica();
    });
});

// Lembretes de ponto: com uma aba do sistema aberta, consulta o servidor e mostra a notificação da batida prevista.
// O servidor decide pelo relógio dele o que vale agora; aqui só se evita repetir o mesmo aviso entre abas.
document.addEventListener('DOMContentLoaded', () => {
    const config = document.querySelector('[data-lembretes-ponto]');
    if (!config || !('Notification' in window)) {
        return;
    }
    const ativar = document.querySelector('[data-lembretes-ativar]');
    const bloqueados = document.querySelector('[data-lembretes-bloqueados]');
    const CHAVE = 'lembretes-ponto-mostrados';
    const mostradosNaMemoria = new Set();
    let temporizador = null;

    const atualizarAvisos = () => {
        if (ativar) ativar.hidden = Notification.permission !== 'default';
        if (bloqueados) bloqueados.hidden = Notification.permission !== 'denied';
    };

    // Marca o aviso como mostrado e diz se ainda não tinha sido; guarda só os avisos do dia.
    const marcarSeNovo = (id) => {
        const dia = id.split('|')[0];
        try {
            const salvo = JSON.parse(localStorage.getItem(CHAVE) || '{}');
            const ids = salvo.dia === dia ? salvo.ids : [];
            if (ids.includes(id)) return false;
            localStorage.setItem(CHAVE, JSON.stringify({ dia, ids: [...ids, id] }));
            return true;
        } catch {
            if (mostradosNaMemoria.has(id)) return false;
            mostradosNaMemoria.add(id);
            return true;
        }
    };

    const notificar = (lembrete) => {
        try {
            const notificacao = new Notification(lembrete.titulo, {
                body: lembrete.corpo,
                tag: lembrete.tag,
                renotify: true,
                icon: config.dataset.icone,
                lang: 'pt-BR',
            });
            notificacao.addEventListener('click', () => {
                window.focus();
                notificacao.close();
                window.location.href = lembrete.destino || config.dataset.destino;
            });
        } catch {
            // Navegadores que só aceitam notificação por service worker (como o Chrome no Android) ficam sem aviso.
        }
    };

    const mostrar = (lembretes) => {
        lembretes.forEach((lembrete) => {
            if (marcarSeNovo(lembrete.id)) notificar(lembrete);
        });
    };

    const consultar = async () => {
        if (Notification.permission !== 'granted') return;
        try {
            const resposta = await fetch(config.dataset.url, {
                headers: { Accept: 'application/json' },
                credentials: 'same-origin',
                cache: 'no-store',
            });
            if (!resposta.ok || !resposta.headers.get('Content-Type')?.includes('application/json')) return;
            const dados = await resposta.json();
            if (!dados.ativo) {
                clearInterval(temporizador);
                return;
            }
            // Duas abas abertas consultam juntas: a trava faz uma de cada vez conferir o que já foi mostrado.
            if (navigator.locks) {
                await navigator.locks.request(CHAVE, () => mostrar(dados.lembretes));
            } else {
                mostrar(dados.lembretes);
            }
        } catch {
            // Sem conexão ou sessão encerrada: tenta de novo na próxima consulta.
        }
    };

    document.querySelector('[data-lembretes-permitir]')?.addEventListener('click', async () => {
        await Notification.requestPermission();
        atualizarAvisos();
        consultar();
    });
    navigator.permissions?.query({ name: 'notifications' }).then((estado) => {
        estado.addEventListener('change', () => {
            atualizarAvisos();
            consultar();
        });
    }).catch(() => {});

    atualizarAvisos();
    consultar();
    temporizador = setInterval(consultar, Number(config.dataset.intervalo) * 1000);
});

// Tema escuro: o botão do cabeçalho alterna e guarda a escolha no navegador. O <head> já aplicou o tema salvo.
document.addEventListener('DOMContentLoaded', () => {
    const botao = document.querySelector('[data-tema-alternar]');
    if (!botao) return;
    const raiz = document.documentElement;
    const atualizarBotao = () => {
        const escuro = raiz.dataset.tema === 'escuro';
        const rotulo = escuro ? 'Ativar tema claro' : 'Ativar tema escuro';
        botao.setAttribute('aria-pressed', String(escuro));
        botao.title = rotulo;
        botao.setAttribute('aria-label', rotulo);
    };
    botao.addEventListener('click', () => {
        const escuro = raiz.dataset.tema !== 'escuro';
        if (escuro) {
            raiz.dataset.tema = 'escuro';
        } else {
            delete raiz.dataset.tema;
        }
        try {
            if (escuro) {
                localStorage.setItem('tema', 'escuro');
            } else {
                localStorage.removeItem('tema');
            }
        } catch {
            // Sem armazenamento (modo restrito do navegador): o tema vale só até trocar de página.
        }
        atualizarBotao();
    });
    // Outra aba trocou o tema: acompanha sem recarregar.
    window.addEventListener('storage', (evento) => {
        if (evento.key !== 'tema') return;
        if (evento.newValue === 'escuro') {
            raiz.dataset.tema = 'escuro';
        } else {
            delete raiz.dataset.tema;
        }
        atualizarBotao();
    });
    atualizarBotao();
});
