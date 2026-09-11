(() => {
  const boot = () => {
    const panel = document.querySelector('#settings .panel');
    if (!panel || document.querySelector('#updatePanel')) return;
    panel.insertAdjacentHTML('beforeend', `<hr><div id="updatePanel" class="update-panel"><div class="row between"><div><div class="eyebrow">LIFECYCLE / GITHUB</div><h3>AI3 Updates</h3><p>Prüft das GitHub-Repository, installiert freigegebene Änderungen und prüft danach den Health-Status.</p></div><span id="updateState" class="badge">● UNKNOWN</span></div><div class="info-grid"><div><span>Aktuell</span><strong id="updateCurrent">—</strong></div><div><span>GitHub</span><strong id="updateRemote">—</strong></div><div><span>Letzter Check</span><strong id="updateTime">—</strong></div></div><label class="toggle-line"><input id="autoUpdate" type="checkbox"><span>Automatische Updates alle 15 Minuten aktivieren</span></label><div class="actions"><button id="updateCheck" class="secondary">↻ Jetzt prüfen</button><button id="updateInstall">⬆ Update installieren</button></div><p id="updateMessage" class="muted">—</p></div>`);

    const stateText = s => ({updated:'● AKTUALISIERT','up-to-date':'● AKTUELL',available:'● UPDATE VERFÜGBAR',updating:'● UPDATE LÄUFT',checking:'● PRÜFUNG',blocked:'● BLOCKIERT',error:'● FEHLER'})[s] || '● UNKNOWN';
    const load = async () => {
      try {
        const d = await api('/__ai3/update/status');
        $('#updateState').textContent = stateText(d.state);
        $('#updateCurrent').textContent = d.current_sha ? d.current_sha.slice(0,12) : '—';
        $('#updateRemote').textContent = d.remote_sha ? d.remote_sha.slice(0,12) : '—';
        $('#updateTime').textContent = d.updated_at ? new Date(d.updated_at).toLocaleString('de-DE') : '—';
        $('#updateMessage').textContent = d.message || '—';
        $('#autoUpdate').checked = !!d.auto_update;
      } catch (e) {
        $('#updateMessage').textContent = 'Updater nicht erreichbar: ' + e.message;
      }
    };
    $('#updateCheck').onclick = async () => { try { await api('/__ai3/update/check', {method:'POST'}); await load(); alert('Update-Check angefordert.'); } catch(e) { alert(e.message); } };
    $('#updateInstall').onclick = async () => { if (!confirm('AI3 jetzt aktualisieren? Der Dienst kann dabei kurz neu starten.')) return; try { await api('/__ai3/update/update', {method:'POST'}); await load(); alert('Update angefordert. Der Host-Timer führt es aus.'); } catch(e) { alert(e.message); } };
    $('#autoUpdate').onchange = async e => { try { await api('/__ai3/update/config', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({auto_update:e.target.checked})}); await load(); } catch(x) { e.target.checked=!e.target.checked; alert(x.message); } };
    load();
    setInterval(load, 30000);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
