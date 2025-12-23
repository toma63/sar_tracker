async function fetchState(){
  try{
    const res = await fetch('/state');
    if(!res.ok) throw new Error(res.statusText);
    return await res.json();
  }catch(e){
    console.error('fetchState failed', e);
    return null;
  }
}

function makeTable(containerId, headers, rows){
  const wrap = document.getElementById(containerId);
  wrap.innerHTML = '';
  const table = document.createElement('table');
  const thead = document.createElement('thead');
  const trh = document.createElement('tr');
  headers.forEach(h=>{const th=document.createElement('th');th.textContent=h;trh.appendChild(th)});
  thead.appendChild(trh);
  table.appendChild(thead);
  const tbody = document.createElement('tbody');
  rows.forEach(r=>{
    const tr = document.createElement('tr');
    r.forEach(c=>{
      const td = document.createElement('td');
      if(c===null || c===undefined) td.textContent='';
      else if(typeof c === 'string' && c.startsWith('{') && c.endsWith('}')){
        td.textContent = c; td.style.fontFamily='monospace';
      } else td.textContent = c;
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  wrap.appendChild(table);
}

function formatTimestamp(ts){
  if(!ts) return '';
  // try parse YYYYmmddTHHMMSSZ
  const m = ts.match(/^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$/);
  if(m){
    const d = new Date(Date.UTC(+m[1],+m[2]-1,+m[3],+m[4],+m[5],+m[6]));
    return d.toISOString().replace('T',' ').replace('Z',' UTC');
  }
  return ts;
}

function renderState(data){
  if(!data) return;
  // Current Status
  const currentHeaders = ['Team','Current Location','Location Status','Transit','Status Code','Updated'];
  const currentRows = [];
  const s = data.status_by_team || {};
  const locs = data.location_by_team || {};
  function formatStatusCode(code){
    if(code === null || code === undefined || code === '') return '';
    // normalize numeric-like values
    const n = Number(code);
    if(!Number.isNaN(n)){
      if(n === 4) return '4 - ok';
      if(n === 6) return '6 - not ok';
      return String(n);
    }
    return String(code);
  }

  function formatLocationStatus(ls){
    if(!ls && ls !== 0) return '';
    try{
      if(typeof ls === 'string' && ls.startsWith('percentage ')){
        // stored as 'percentage 60%'; display only '60%'
        return ls.split(' ')[1] || ls;
      }
    }catch(e){
      // fallthrough
    }
    return String(ls);
  }

  Object.keys(s).sort().forEach(team=>{
    const history = s[team] || [];
    const current = history.length ? history[history.length-1] : null;
    const updated = current ? formatTimestamp(current.timestamp) : '';
    currentRows.push([team, locs[team] || '', current ? formatLocationStatus(current.location_status) : '', current ? current.transit : '', current ? formatStatusCode(current.status_code) : '', updated]);
  });
  makeTable('current-status', currentHeaders, currentRows);
  
  // Status History
  const histHeaders = ['Team','Timestamp','Location','Location Status','Transit','Status Code'];
  const histRows = [];
  try{
    Object.keys(s).sort().forEach(team=>{
      (s[team]||[]).forEach(e=>{
        histRows.push([team, formatTimestamp(e.timestamp), e.location, formatLocationStatus(e.location_status), e.transit, formatStatusCode(e.status_code)]);
      })
    });
  }catch(err){
    console.error('Error building status history rows', err);
  }
  makeTable('status-history', histHeaders, histRows);

  // Transmissions
  const txHeaders = ['Timestamp','Dest','Src','Message'];
  const txRows = (data.transmissions||[]).map(t=>[formatTimestamp(t.timestamp), t.dest, t.src, t.msg]);
  makeTable('transmissions', txHeaders, txRows);

  const lu = document.getElementById('last-updated');
  lu.textContent = 'Last loaded: ' + (new Date()).toLocaleString();
}

async function refresh(){
  const data = await fetchState();
  if(data) renderState(data);
}

document.addEventListener('DOMContentLoaded', ()=>{
  document.getElementById('reload').addEventListener('click', refresh);
  refresh();
});
