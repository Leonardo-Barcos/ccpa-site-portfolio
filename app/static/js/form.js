/* CCPA — abas, máscaras e busca de CEP. Sem dependências externas. */
(() => {
  "use strict";

  /* ------------------------------ Abas ------------------------------ */
  const abas = document.querySelectorAll('.aba[role="tab"]');
  abas.forEach((aba) => {
    aba.addEventListener("click", () => {
      abas.forEach((outra) => {
        const ativa = outra === aba;
        outra.setAttribute("aria-selected", String(ativa));
        const painel = document.getElementById(outra.getAttribute("aria-controls"));
        if (painel) painel.hidden = !ativa;
      });
      history.replaceState(null, "", aba.id === "tab-pj" ? "?tipo=pj#formulario"
                                                         : "?tipo=pf#formulario");
    });
  });

  /* ---------------------------- Máscaras ---------------------------- */
  const digitos = (v) => v.replace(/\D/g, "");

  const mascaras = {
    cpf: (v) => digitos(v).slice(0, 11)
      .replace(/(\d{3})(\d)/, "$1.$2")
      .replace(/(\d{3})(\d)/, "$1.$2")
      .replace(/(\d{3})(\d{1,2})$/, "$1-$2"),

    cnpj: (v) => digitos(v).slice(0, 14)
      .replace(/^(\d{2})(\d)/, "$1.$2")
      .replace(/^(\d{2})\.(\d{3})(\d)/, "$1.$2.$3")
      .replace(/\.(\d{3})(\d)/, ".$1/$2")
      .replace(/(\d{4})(\d{1,2})$/, "$1-$2"),

    cep: (v) => digitos(v).slice(0, 8).replace(/^(\d{5})(\d)/, "$1-$2"),

    telefone: (v) => {
      const d = digitos(v).slice(0, 11);
      if (d.length <= 10) {
        return d.replace(/^(\d{2})(\d)/, "($1) $2").replace(/(\d{4})(\d{1,4})$/, "$1-$2");
      }
      return d.replace(/^(\d{2})(\d)/, "($1) $2").replace(/(\d{5})(\d{1,4})$/, "$1-$2");
    },
  };

  const aplicar = (seletor, fn) => {
    document.querySelectorAll(seletor).forEach((el) => {
      el.addEventListener("input", () => { el.value = fn(el.value); });
    });
  };

  aplicar('input[name="cpf"]', mascaras.cpf);
  aplicar('input[name="cnpj"]', mascaras.cnpj);
  aplicar('input[name="postal_code"]', mascaras.cep);
  aplicar('input[name="mobile"], input[name="secondary_phone"]', mascaras.telefone);

  /* ------------------------- Busca de CEP --------------------------- */
  document.querySelectorAll('input[name="postal_code"]').forEach((campoCep) => {
    campoCep.addEventListener("blur", async () => {
      const cep = digitos(campoCep.value);
      if (cep.length !== 8) return;
      const form = campoCep.closest("form");
      try {
        const r = await fetch(`https://viacep.com.br/ws/${cep}/json/`);
        const d = await r.json();
        if (d.erro) return;
        const set = (nome, valor) => {
          const el = form.querySelector(`[name="${nome}"]`);
          if (el && !el.value) el.value = valor || "";
        };
        set("street", d.logradouro);
        set("district", d.bairro);
        set("city", d.localidade);
        const uf = form.querySelector('[name="state"]');
        if (uf && !uf.value) uf.value = d.uf || "";
        const numero = form.querySelector('[name="number"]');
        if (numero && !numero.value) numero.focus();
      } catch (_) { /* offline: o usuário preenche à mão */ }
    });
  });

  /* --------------- Confirmação de senha em tempo real --------------- */
  document.querySelectorAll("form").forEach((form) => {
    const senha = form.querySelector('input[name="password"]');
    const conf = form.querySelector('input[name="password_confirmation"]');
    if (!senha || !conf) return;
    const checar = () => {
      conf.setCustomValidity(
        conf.value && conf.value !== senha.value ? "As senhas não conferem." : ""
      );
    };
    senha.addEventListener("input", checar);
    conf.addEventListener("input", checar);

    form.addEventListener("submit", (ev) => {
      if (!form.checkValidity()) {
        ev.preventDefault();
        const invalido = form.querySelector(":invalid");
        if (invalido) { invalido.focus(); invalido.reportValidity?.(); }
        return;
      }
      const botao = form.querySelector('button[type="submit"]');
      if (botao) { botao.disabled = true; botao.textContent = "Enviando..."; }
    });
  });

  /* Rola até o formulário quando a página volta com erros */
  if (document.querySelector(".alerta")) {
    document.getElementById("formulario")?.scrollIntoView({ behavior: "smooth" });
  }
})();
