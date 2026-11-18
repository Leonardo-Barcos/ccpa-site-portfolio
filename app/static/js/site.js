/* CCPA — comportamentos do site. Sem dependências. */
(() => {
  "use strict";

  /* ------------------------- Menu no celular ------------------------- */
  const botao = document.querySelector(".menu__botao");
  const menu = document.getElementById("menu-principal");

  if (botao && menu) {
    const estreito = () => window.matchMedia("(max-width: 940px)").matches;

    const aplicar = () => {
      if (estreito()) {
        const aberto = botao.getAttribute("aria-expanded") === "true";
        menu.hidden = !aberto;
      } else {
        menu.hidden = false;
        botao.setAttribute("aria-expanded", "false");
      }
    };

    botao.addEventListener("click", () => {
      const aberto = botao.getAttribute("aria-expanded") === "true";
      botao.setAttribute("aria-expanded", String(!aberto));
      botao.setAttribute("aria-label", aberto ? "Abrir menu" : "Fechar menu");
      aplicar();
    });

    document.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape" && botao.getAttribute("aria-expanded") === "true") {
        botao.setAttribute("aria-expanded", "false");
        aplicar();
        botao.focus();
      }
    });

    window.addEventListener("resize", aplicar);
    aplicar();
  }

  /* ---------------- Confirmação antes de excluir no admin ------------- */
  document.querySelectorAll("form[data-confirmar]").forEach((form) => {
    form.addEventListener("submit", (ev) => {
      if (!window.confirm(form.dataset.confirmar)) ev.preventDefault();
    });
  });

  /* ------------------ Evita envio duplo em formulários ---------------- */
  document.querySelectorAll("form[method='post']").forEach((form) => {
    form.addEventListener("submit", () => {
      const botaoEnvio = form.querySelector("button[type='submit']");
      if (botaoEnvio && form.checkValidity()) {
        setTimeout(() => {
          botaoEnvio.disabled = true;
          botaoEnvio.textContent = "Enviando...";
        }, 0);
      }
    });
  });
})();
