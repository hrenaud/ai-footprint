document.querySelectorAll(".install-cmd-wrap").forEach((wrap) => {
  const code = document.getElementById(wrap.dataset.copyTarget);
  const feedback = wrap.querySelector(".copy-feedback");
  wrap.addEventListener("click", async () => {
    await navigator.clipboard.writeText(code.textContent);
    feedback.textContent = wrap.dataset.copiedLabel;
    feedback.classList.add("visible");
    setTimeout(() => {
      feedback.classList.remove("visible");
    }, 2000);
  });
});
