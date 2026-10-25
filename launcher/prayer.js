(function (root) {
  'use strict';
  var settings = (root.LAUNCHER_LOCAL && root.LAUNCHER_LOCAL.prayer) || {};
  var ZONE = /^[A-Z]{3}\d{2}$/.test(settings.zone || '') ? settings.zone : 'SGR01';
  var MONTHS = {jan:1,feb:2,mac:3,mar:3,apr:4,mei:5,may:5,jun:6,jul:7,ogo:8,ogos:8,aug:8,sep:9,okt:10,oct:10,nov:11,dis:12,dec:12};
  var TIMES = [['fajr','Subuh'],['syuruk','Syuruk'],['dhuhr','Zohor'],['asr','Asar'],['maghrib','Maghrib'],['isha','Isyak']];
  function pad(n) { return ('0' + n).slice(-2); }
  function iso(ms) { return new Date(ms + 8 * 3600000).toISOString().slice(0,10); }
  function dateKey(value) {
    var m = /^(\d{2})-([A-Za-z]+)-(\d{4})$/.exec(value || '');
    var month = m && MONTHS[m[2].toLowerCase()];
    return month ? m[3] + '-' + pad(month) + '-' + m[1] : null;
  }
  function epoch(day, time) { return Date.parse(day + 'T' + time + '+08:00'); }
  function normalize(data) {
    var rows = {};
    if (!data || data.zone !== ZONE || !Array.isArray(data.prayerTime)) throw new Error('Invalid zone/timetable');
    data.prayerTime.forEach(function (row) {
      var day = dateKey(row.date);
      if (day && TIMES.every(function (p) { return /^\d{2}:\d{2}:\d{2}$/.test(row[p[0]] || '') && isFinite(epoch(day, row[p[0]])); })) rows[day] = row;
    });
    return rows;
  }
  function upcoming(rows, now) {
    var today = iso(now), tomorrow = iso(now + 86400000);
    var result = null;
    [today,tomorrow].forEach(function (day) {
      var row = rows[day];
      if (!row) return;
      TIMES.forEach(function (p) {
        if (p[0] === 'syuruk') return;
        var at = epoch(day,row[p[0]]);
        if (at > now && (!result || at < result.at)) result = {key:p[0],label:p[1],at:at,day:day,time:row[p[0]].slice(0,5)};
      });
    });
    return result;
  }
  root.SOLAT_UTILS = {dateKey:dateKey,iso:iso,normalize:normalize,upcoming:upcoming};
  if (!root.document) return;
  if (settings.enabled === false) { document.getElementById('solat').style.display = 'none'; return; }
  document.querySelector('#solat .solat-heading p').textContent = (settings.place || ZONE) + ' · ' + ZONE;
  document.getElementById('solat').setAttribute('aria-label', 'Waktu solat ' + (settings.place || ZONE));
  var rows = {}, loading = false, lastAttempt = 0, lastSuccess = 0, renderedDay = '';
  var list = document.getElementById('solat-times'), status = document.getElementById('solat-status'), nextEl = document.getElementById('solat-next');
  function merge(data) {
    var incoming = normalize(data);
    Object.keys(incoming).forEach(function (day) { rows[day] = incoming[day]; });
  }
  try { merge(root.SOLAT_BUNDLED); } catch (e) {}
  try { merge(JSON.parse(localStorage.getItem('solat.' + ZONE) || 'null')); } catch (e) {}
  function render() {
    var now = Date.now(), day = iso(now), row = rows[day], next = upcoming(rows,now);
    if (!row) {
      list.textContent = '';
      nextEl.textContent = 'Jadual hari ini belum tersedia';
      status.textContent = 'JAKIM e-Solat · Semak sambungan internet';
      return;
    }
    if (renderedDay !== day) {
      list.textContent = '';
      TIMES.forEach(function (p) {
        var tile = document.createElement('div'); tile.className = 'solat-time'; tile.dataset.key = p[0];
        var label = document.createElement('span'); label.textContent = p[1];
        var time = document.createElement('strong'); time.textContent = row[p[0]].slice(0,5);
        tile.appendChild(label); tile.appendChild(time); list.appendChild(tile);
      });
      renderedDay = day;
    }
    Array.prototype.forEach.call(list.children,function (tile) { tile.classList.toggle('next',Boolean(next && next.day === day && tile.dataset.key === next.key)); });
    if (next) {
      var mins = Math.ceil((next.at-now)/60000), hours = Math.floor(mins/60);
      nextEl.textContent = 'Seterusnya: ' + next.label + (next.day !== day ? ' esok' : '') + ' · ' + next.time + ' · ' + (hours ? hours + 'j ' : '') + mins%60 + 'm';
    } else nextEl.textContent = 'Semua waktu hari ini telah berlalu';
    status.textContent = 'JAKIM e-Solat · ' + day + ' · Waktu Malaysia' + (!lastSuccess ? ' · Jadual tersimpan' : '');
  }
  function refresh() {
    var now = Date.now();
    if (loading || now-lastAttempt < 300000 || (lastSuccess && now-lastSuccess < 21600000 && rows[iso(now)])) return;
    loading = true; lastAttempt = now;
    var xhr = new XMLHttpRequest();
    xhr.open('GET','https://www.e-solat.gov.my/index.php?r=esolatApi/takwimsolat&period=year&zone=' + ZONE,true);
    xhr.timeout = 15000;
    xhr.onload = function () {
      loading = false;
      try {
        if (xhr.status !== 200) throw new Error('HTTP');
        var data = JSON.parse(xhr.responseText); merge(data);
        if (!rows[iso(Date.now())]) throw new Error('Missing current day');
        lastSuccess = Date.now(); renderedDay = '';
        try { localStorage.setItem('solat.' + ZONE,JSON.stringify(data)); } catch (e) {}
      } catch (e) {}
      render();
    };
    xhr.onerror = xhr.ontimeout = function () { loading = false; render(); };
    xhr.send();
  }
  render(); refresh();
  setInterval(function () { render(); refresh(); },30000);
  document.addEventListener('visibilitychange',function () { if (!document.hidden) { render(); refresh(); } });
})(typeof window !== 'undefined' ? window : globalThis);
