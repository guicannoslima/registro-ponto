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
        const data = (dataHora.value || '').slice(0, 10) || painel.dataset.hoje;
        const parametros = new URLSearchParams({ parcial: '1', funcionario: funcionario.value, data });
        fetch(`${painel.dataset.url}?${parametros}`)
            .then((resposta) => (resposta.ok ? resposta.text() : Promise.reject(resposta.status)))
            .then((html) => {
                painel.innerHTML = html;
            })
            .catch(() => {
                // Sem o painel atualizado o formulário continua funcionando normalmente.
            });
    };

    funcionario.addEventListener('change', atualizar);
    dataHora.addEventListener('change', atualizar);
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
