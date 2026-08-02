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

document.querySelectorAll('[role="tablist"]').forEach((tabList) => {
  const tabs = [...tabList.querySelectorAll('[role="tab"]')];
  const activateTab = (tab) => {
    tabs.forEach((candidate) => {
      const selected = candidate === tab;
      const panel = document.getElementById(candidate.getAttribute("aria-controls"));
      candidate.setAttribute("aria-selected", String(selected));
      candidate.tabIndex = selected ? 0 : -1;
      panel.hidden = !selected;
    });
  };

  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => activateTab(tab));
    tab.addEventListener("keydown", (event) => {
      let nextIndex;
      if (event.key === "ArrowLeft") nextIndex = (index - 1 + tabs.length) % tabs.length;
      if (event.key === "ArrowRight") nextIndex = (index + 1) % tabs.length;
      if (event.key === "Home") nextIndex = 0;
      if (event.key === "End") nextIndex = tabs.length - 1;
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        activateTab(tab);
        return;
      }
      if (nextIndex === undefined) return;
      event.preventDefault();
      tabs[nextIndex].focus();
      activateTab(tabs[nextIndex]);
    });
  });
});
