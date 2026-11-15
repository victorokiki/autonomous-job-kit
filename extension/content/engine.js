/*
 * Autonomous Job Kit Autofill - the fill run.
 *
 * run({profile, resume}) -> Promise<summary>
 *   summary = { controls, filled, already, left, leftItems: [text], report: 'Autonomous report: ...' }
 * opts.profileMeta = {source: 'imported'|'saved', date: 'YYYY-MM-DD'} (written by the options page).
 *
 * Steps: collect fields -> write the "still filling" report -> for each field in page order:
 * skip if it already has a value, ask rules.decide(), apply with setters -> a second short pass
 * for fields that appeared after answers (Workday-style follow-ups) -> marks, report, panel.
 * Never clicks Next/Submit; never changes a field that already has a value, so running twice is safe.
 */
(function (root) {
  'use strict';
  var JK = root.JobKit = root.JobKit || {};

  var running = false;

  function item(f, extra) {
    var o = { label: f.q.text || '(unlabelled ' + f.kind + ')', kind: f.kind, required: !!f.required };
    if (extra) for (var k in extra) o[k] = extra[k];
    return o;
  }

  async function processFields(fields, ctx) {
    for (var i = 0; i < fields.length; i++) {
      var f = fields[i];
      if (ctx.seen.has(f.el)) continue;
      ctx.seen.add(f.el);
      (f.els || []).forEach(function (e) { ctx.seen.add(e); });
      if (!f.el.isConnected) continue;

      if (JK.labels.hasValue(f)) { ctx.res.already.push(item(f)); continue; }

      var d = JK.rules.decide(f.q, ctx.profile, ctx.env);
      if (!d.ok) {
        ctx.res.left.push(item(f, { reason: d.reason, rule: d.rule }));
        JK.ui.mark(f, 'left');
        continue;
      }
      var out;
      try {
        out = await JK.setters.apply(f, d.want, { resume: ctx.resume, resumeSkipped: ctx.resumeSkipped });
      } catch (e) {
        out = { ok: false, reason: 'error' };
      }
      if (f.kind === 'combobox' || f.kind === 'listbox' || f.kind === 'radio') ctx.changedLayout = true;
      if (out.ok) {
        ctx.res.filled.push(item(f, { value: out.value, rule: d.rule }));
        JK.ui.mark(f, 'filled');
      } else if (!out.quiet) {
        ctx.res.left.push(item(f, { reason: out.reason, rule: d.rule }));
        JK.ui.mark(f, 'left');
      }
    }
  }

  function summary(res, fieldsCount, freshness) {
    var text = JK.ui.reportText(res, freshness);
    return {
      controls: fieldsCount,
      filled: res.filled.length,
      already: res.already.length,
      left: res.left.length,
      leftItems: res.left.map(function (i) { return i.label; }),
      report: text,
      details: res
    };
  }

  async function run(opts) {
    if (running) return { busy: true, report: JK.ui.WORKING_TEXT };
    running = true;
    JK.ui.setBusy(true);
    try {
      var profile = (opts && opts.profile) || {};
      var fields = JK.labels.collect(document);
      if (!fields.length) return { controls: 0, filled: 0, already: 0, left: 0, leftItems: [], report: '' };

      JK.ui.working(fields);
      JK.ui.clearMarks('left');

      var hasPhoneCode = fields.some(function (f) {
        var d = JK.rules.decide(f.q, profile, {});
        return d.rule === 'phone country code';
      });
      var ctx = {
        profile: profile, resume: opts && opts.resume,
        // The page button is what Claude clicks after tailoring a resume for this job, so it leaves the upload for
        // the tailored PDF; the popup and the keyboard shortcut (the user's own fills) attach the stored resume.
        resumeSkipped: !!(opts && opts.trigger === 'button'), env: { hasPhoneCode: hasPhoneCode },
        seen: new Set(), changedLayout: false,
        res: { filled: [], already: [], left: [] }
      };

      await processFields(fields, ctx);
      if (ctx.changedLayout) {
        await JK.setters.sleep(400);
        var more = JK.labels.collect(document).filter(function (f) { return !ctx.seen.has(f.el); });
        if (more.length) await processFields(more, ctx);
      }

      var s = summary(ctx.res, fields.length, JK.ui.freshness(profile, opts && opts.profileMeta));
      JK.ui.setReport(s.report, fields);
      JK.ui.showPanel(ctx.res);
      return s;
    } finally {
      running = false;
      JK.ui.setBusy(false);
    }
  }

  JK.engine = { run: run, isRunning: function () { return running; } };
})(typeof globalThis !== 'undefined' ? globalThis : this);
