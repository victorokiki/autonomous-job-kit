/*
 * Autonomous Job Kit Autofill - toolbar popup: "Fill this page", "Edit profile" and a short status.
 * The fill itself runs in the service worker (background.js fillTab) so the popup can close early.
 */
(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };

  function say(msg, kind) {
    var s = $('status');
    s.textContent = msg;
    s.className = kind || '';
  }

  async function showProfile() {
    var data = await chrome.storage.local.get(['profile', 'resume']);
    var p = data.profile || {};
    var name = [p.preferredName || p.firstName, p.lastName].filter(Boolean).join(' ');
    var line;
    if (!Object.keys(p).length) {
      line = 'No profile yet. Choose "Edit profile" to import profile.json.';
      $('fill').disabled = true;
    } else {
      line = 'Profile: ' + (name || 'saved') + (data.resume && data.resume.data ? ' · resume PDF saved' : ' · no resume PDF');
    }
    $('profile-line').textContent = line;
  }

  $('edit').addEventListener('click', function () {
    chrome.runtime.openOptionsPage();
    window.close();
  });

  $('fill').addEventListener('click', async function () {
    var btn = $('fill');
    btn.disabled = true;
    say('Filling…', '');
    try {
      var tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tabs[0]) throw new Error('No active tab.');
      var r = await chrome.runtime.sendMessage({ type: 'jobkit:fill-tab', tabId: tabs[0].id });
      if (!r) throw new Error('No answer from the extension.');
      if (r.error) { say(r.error, 'err'); return; }
      if (r.noProfile && !r.frames) { say('No profile saved yet. Choose "Edit profile".', 'warn'); return; }
      if (!r.frames) { say('No form found on this page.', 'warn'); return; }
      if (r.busy) { say('Already filling; wait a moment.', 'warn'); return; }
      say('Filled ' + r.filled + ', left ' + r.left + ' for you' + (r.already ? ', ' + r.already + ' already filled' : '') + '. Nothing was submitted.', 'ok');
    } catch (e) {
      say('Could not fill this page: ' + (e && e.message ? e.message : e), 'err');
    } finally {
      btn.disabled = false;
    }
  });

  showProfile();
})();
