/*
 * Small imitations of the custom controls real application systems use, for the fixtures:
 *  - .rs   react-select style combobox: <input role="combobox" aria-controls> + listbox of
 *          role="option" divs that opens on mousedown / ArrowDown / typing, picks on click.
 *  - .wd   Workday style listbox button: <button aria-haspopup="listbox"> + <ul role="listbox">.
 *  - [data-controlled]  a "controlled" input like React's: the value only sticks when an input
 *          event reports it; on blur the element is reset to the framework's state.
 * Options come from data-options="A|B|C". Picking dispatches a bubbling "widget-change" event.
 */
(function () {
  'use strict';
  window.JK_STATE = {};

  function opts(host) { return host.getAttribute('data-options').split('|'); }

  document.querySelectorAll('.rs').forEach(function (host) {
    var input = host.querySelector('input[role="combobox"]');
    var list = document.getElementById(input.getAttribute('aria-controls'));
    var value = host.querySelector('.rs-single-value');
    function render() {
      var q = input.value.toLowerCase();
      list.innerHTML = '';
      opts(host).filter(function (o) { return !q || o.toLowerCase().indexOf(q) !== -1; }).forEach(function (o, i) {
        var d = document.createElement('div');
        d.setAttribute('role', 'option');
        d.id = list.id + '-o' + i;
        d.textContent = o;
        d.addEventListener('click', function () {
          value.textContent = o;
          input.value = '';
          list.hidden = true;
          input.setAttribute('aria-expanded', 'false');
          host.dispatchEvent(new CustomEvent('widget-change', { bubbles: true, detail: o }));
        });
        list.appendChild(d);
      });
      list.hidden = false;
      input.setAttribute('aria-expanded', 'true');
    }
    input.addEventListener('mousedown', render);
    input.addEventListener('input', render);
    input.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowDown') render();
      if (e.key === 'Escape') { list.hidden = true; }
    });
  });

  document.querySelectorAll('.wd').forEach(function (host) {
    var btn = host.querySelector('button[aria-haspopup="listbox"]');
    var list = document.getElementById(btn.getAttribute('aria-controls'));
    btn.addEventListener('click', function () {
      list.innerHTML = '';
      opts(host).forEach(function (o, i) {
        var li = document.createElement('li');
        li.setAttribute('role', 'option');
        li.id = list.id + '-o' + i;
        li.textContent = o;
        li.addEventListener('click', function () {
          btn.textContent = o;
          list.hidden = true;
          btn.setAttribute('aria-expanded', 'false');
          host.dispatchEvent(new CustomEvent('widget-change', { bubbles: true, detail: o }));
        });
        list.appendChild(li);
      });
      list.hidden = !list.hidden;
      btn.setAttribute('aria-expanded', String(!list.hidden));
    });
    list.addEventListener('keydown', function (e) { if (e.key === 'Escape') list.hidden = true; });
  });

  // Like React's value tracker: a plain `el.value = x` updates the tracked value, so the next
  // input event looks like "no change" and the framework state stays old (then blur reverts it).
  // Only the prototype's native setter + input event gets through.
  document.querySelectorAll('[data-controlled]').forEach(function (el) {
    var key = el.getAttribute('data-controlled');
    var proto = Object.getPrototypeOf(el);
    var desc = Object.getOwnPropertyDescriptor(proto, 'value');
    var tracked = desc.get.call(el);
    window.JK_STATE[key] = tracked;
    Object.defineProperty(el, 'value', {
      configurable: true,
      get: function () { return desc.get.call(this); },
      set: function (v) { tracked = String(v); desc.set.call(this, v); }
    });
    el.addEventListener('input', function () {
      var cur = desc.get.call(el);
      if (cur !== tracked) { tracked = cur; window.JK_STATE[key] = cur; }
    });
    el.addEventListener('blur', function () {
      if (desc.get.call(el) !== window.JK_STATE[key]) { desc.set.call(el, window.JK_STATE[key]); tracked = window.JK_STATE[key]; }
    });
  });
})();
