/* Progressive enhancement only.
 *
 * With JavaScript off the transfer details are already open and every value is
 * selectable by hand, so the failure mode is "shows more at once", never
 * "cannot pay". Nothing here is required to complete a transfer.
 */
(function () {
  "use strict";

  var toast = document.querySelector("[data-toast]");
  var toastTimer;

  function flash(message) {
    if (!toast) return;
    toast.textContent = message;
    toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { toast.hidden = true; }, 1600);
  }

  function copy(text) {
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(
        function () { flash("Đã chép"); },
        function () { flash("Không chép được, hãy chọn và chép tay"); }
      );
      return;
    }
    // Older mobile browsers, and any page not served over HTTPS.
    var field = document.createElement("textarea");
    field.value = text;
    field.setAttribute("readonly", "");
    field.style.position = "fixed";
    field.style.opacity = "0";
    document.body.appendChild(field);
    field.select();
    try {
      flash(document.execCommand("copy") ? "Đã chép" : "Không chép được, hãy chọn và chép tay");
    } catch (error) {
      flash("Không chép được, hãy chọn và chép tay");
    }
    document.body.removeChild(field);
  }

  document.addEventListener("click", function (event) {
    var copyTarget = event.target.closest("[data-copy]");
    if (copyTarget) {
      copy(copyTarget.getAttribute("data-copy"));
      return;
    }
    var reveal = event.target.closest("[data-reveal]");
    if (reveal) {
      var card = reveal.closest(".card");
      var panel = card && card.querySelector("[data-transfer]");
      if (panel) {
        panel.hidden = false;
        reveal.hidden = true;
        panel.scrollIntoView({ block: "nearest", behavior: "smooth" });
      }
    }
  });

  // Collapse the transfer panel only once JS is confirmed working, so a script
  // error leaves the page usable rather than empty.
  document.querySelectorAll("[data-transfer]").forEach(function (panel) {
    panel.hidden = true;
  });
})();
