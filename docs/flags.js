/* 安托萨开关（静态页面版）——Hark（CS线）
 * 用法：页面里 <script src="（相对路径）/flags.js"></script>，然后
 *   if (AFlag.on('名字')) { 新行为 } else { 旧行为 }
 * URL：?flag=a,b 打开（记在 localStorage，下次还在）；?flag=-a 关闭；?flag=clear 全清。
 * 未在 flags.json 登记或已过期的开关一律当作关闭。
 */
(function (w) {
  var KEY = 'anthousa.flags';
  var on = {};
  try { (JSON.parse(w.localStorage.getItem(KEY) || '[]')).forEach(function (n) { on[n] = 1; }); } catch (e) {}
  var q = new URLSearchParams(w.location.search).get('flag');
  if (q) q.split(',').forEach(function (s) {
    s = s.trim(); if (!s) return;
    if (s === 'clear') on = {}; else if (s[0] === '-') delete on[s.slice(1)]; else on[s] = 1;
  });
  try { w.localStorage.setItem(KEY, JSON.stringify(Object.keys(on))); } catch (e) {}

  var reg = null, today = new Date().toISOString().slice(0, 10);
  var src = (document.currentScript && document.currentScript.src) || 'flags.js';
  var url = src.replace(/flags\.js(\?.*)?$/, 'flags.json');
  try { // 同步读，保证页面第一行代码就能判断
    var x = new XMLHttpRequest(); x.open('GET', url, false); x.send();
    if (x.status === 200 || x.status === 0) { reg = {}; JSON.parse(x.responseText).flags.forEach(function (f) { reg[f.name] = f; }); }
  } catch (e) { reg = null; }

  function valid(n) { var f = reg && reg[n]; return !!f && (!f.expires || f.expires >= today); }
  var AFlag = {
    on: function (n) { return !!on[n] && valid(n); },
    active: function () { return Object.keys(on).filter(valid); },
    registry: function () { return reg; }
  };
  w.AFlag = AFlag;

  if (AFlag.on('flag-badge')) {
    var show = function () {
      var b = document.createElement('div');
      b.textContent = '灰度 · ' + AFlag.active().join(', ');
      b.style.cssText = 'position:fixed;right:8px;bottom:8px;z-index:99999;padding:4px 8px;font:12px/1.4 sans-serif;color:#fff;background:rgba(200,60,40,.85);border-radius:4px;pointer-events:none';
      document.body.appendChild(b);
    };
    if (document.body) show(); else document.addEventListener('DOMContentLoaded', show);
  }
})(window);
