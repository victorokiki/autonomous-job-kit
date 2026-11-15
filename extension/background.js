/*
 * Job Kit Autofill - service worker.
 *
 * - Alt+Shift+F (command "fill-page") and the popup's "Fill this page" both call fillTab():
 *   it injects the content scripts into frames that do not have them yet (activeTab +
 *   scripting, for sites outside the built-in list), then runs JobKit.startFill() in every
 *   frame and adds up the results.
 * - Opens the options page after first install.
 * No network requests are made anywhere in the extension.
 */
'use strict';

// Keep in the same order as manifest.json content_scripts.js (tests/extension/check.js verifies).
const CONTENT_FILES = [
  'content/text.js',
  'content/rules.js',
  'content/labels.js',
  'content/setters.js',
  'content/ui.js',
  'content/engine.js',
  'content/main.js'
];

async function frameHasKit(tabId) {
  const res = await chrome.scripting.executeScript({
    target: { tabId, allFrames: true },
    func: () => !!(globalThis.JobKit && globalThis.JobKit.startFill)
  });
  return res;
}

async function fillTab(tabId, trigger) {
  let probe;
  try {
    probe = await frameHasKit(tabId);
  } catch (e) {
    return { error: 'Job Kit cannot run on this page (browser pages, the Web Store and PDF viewers are off limits).' };
  }
  const missing = probe.filter((r) => !r.result).map((r) => r.frameId);
  if (missing.length) {
    try {
      await chrome.scripting.executeScript({ target: { tabId, frameIds: missing }, files: CONTENT_FILES });
    } catch (e) {
      // Some frames may refuse injection; fill the ones we can.
    }
  }
  let results = [];
  try {
    results = await chrome.scripting.executeScript({
      target: { tabId, allFrames: true },
      func: (t) => (globalThis.JobKit && globalThis.JobKit.startFill ? globalThis.JobKit.startFill(t) : null),
      args: [trigger || 'shortcut']
    });
  } catch (e) {
    return { error: 'Could not fill this page: ' + (e && e.message ? e.message : e) };
  }
  const total = { frames: 0, filled: 0, already: 0, left: 0, leftItems: [], noProfile: false };
  for (const r of results) {
    const s = r && r.result;
    if (!s || !s.controls) { if (s && s.noProfile) total.noProfile = true; continue; }
    total.frames += 1;
    total.filled += s.filled || 0;
    total.already += s.already || 0;
    total.left += s.left || 0;
    total.leftItems = total.leftItems.concat(s.leftItems || []);
    if (s.busy) total.busy = true;
  }
  if (total.frames) {
    chrome.action.setBadgeBackgroundColor({ tabId, color: '#1b7f3b' }).catch(() => {});
    chrome.action.setBadgeText({ tabId, text: String(total.filled) }).catch(() => {});
  }
  return total;
}

chrome.commands.onCommand.addListener(async (command, tab) => {
  if (command !== 'fill-page') return;
  const target = tab && tab.id ? tab : (await chrome.tabs.query({ active: true, currentWindow: true }))[0];
  if (target && target.id) fillTab(target.id, 'shortcut');
});

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (!msg || sender.id !== chrome.runtime.id) return false;
  if (msg.type === 'jobkit:fill-tab' && typeof msg.tabId === 'number') {
    fillTab(msg.tabId, 'popup').then(sendResponse, (e) => sendResponse({ error: String(e) }));
    return true;
  }
  return false;
});

chrome.runtime.onInstalled.addListener(async (details) => {
  if (details.reason !== 'install') return;
  const { profile } = await chrome.storage.local.get('profile');
  if (!profile) chrome.runtime.openOptionsPage();
});
