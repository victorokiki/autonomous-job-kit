/*
 * Job Kit Autofill - content script entry point (loaded last).
 *
 * Loads the profile from chrome.storage.local, shows the page button when the page has a form
 * (and the "show page button" setting is on), and answers fill requests from the service worker
 * (popup "Fill this page" and the Alt+Shift+F shortcut). Safe to inject more than once.
 *
 * Exposes JobKit.startFill(trigger) -> Promise<summary> (see engine.js).
 */
(function (root) {
  'use strict';
  var JK = root.JobKit = root.JobKit || {};
  if (JK.booted) return;
  JK.booted = true;

  var hasChrome = typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local;

  function load() {
    if (!hasChrome) return Promise.resolve({});
    return chrome.storage.local.get(['profile', 'profileMeta', 'resume', 'settings']).catch(function () { return {}; });
  }

  async function startFill(trigger) {
    var data = await load();
    var profile = data.profile;
    if (!profile || typeof profile !== 'object' || !Object.keys(profile).length) {
      if (!JK.labels.looksLikeForm(document)) return { controls: 0, noProfile: true };
      var msg = 'Job Kit report: no profile saved yet. Open Job Kit Autofill options (Edit profile) and import profile.json, then fill again.';
      JK.ui.setReport(msg, []);
      JK.ui.showPanel(null, 'No profile saved yet. Open the extension menu, choose "Edit profile" and import your profile.json, then try again.');
      return { controls: 0, noProfile: true, report: msg };
    }
    return JK.engine.run({ profile: profile, profileMeta: data.profileMeta, resume: data.resume, trigger: trigger });
  }
  JK.startFill = startFill;

  var showSetting = true;
  var checkTimer = null;

  function refreshButton() {
    checkTimer = null;
    var show = showSetting && JK.labels.looksLikeForm(document);
    JK.ui.showButton(show, function () { startFill('button'); });
  }

  function scheduleCheck() {
    if (!checkTimer) checkTimer = setTimeout(refreshButton, 800);
  }

  load().then(function (data) {
    showSetting = !(data.settings && data.settings.showButton === false);
    refreshButton();
    if (root.MutationObserver && document.documentElement) {
      new MutationObserver(function (records) {
        for (var i = 0; i < records.length; i++) {
          var t = records[i].target;
          if (!(t.closest && t.closest('[data-jobkit-ui]'))) { scheduleCheck(); return; }
        }
      }).observe(document.documentElement, { childList: true, subtree: true });
    }
  });

  if (hasChrome) {
    chrome.storage.onChanged.addListener(function (changes, area) {
      if (area === 'local' && changes.settings) {
        var s = changes.settings.newValue || {};
        showSetting = s.showButton !== false;
        refreshButton();
      }
    });
    chrome.runtime.onMessage.addListener(function (msg, sender, sendResponse) {
      if (!msg || msg.type !== 'jobkit:fill' || sender.id !== chrome.runtime.id) return false;
      startFill(msg.trigger || 'message').then(sendResponse, function (e) { sendResponse({ error: String(e) }); });
      return true;
    });
  }
})(typeof globalThis !== 'undefined' ? globalThis : this);
