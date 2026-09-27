// Applies a saved light/dark choice before first paint; dark is the default.
try{const t=localStorage.getItem('tracker-theme');if(t==='light'||t==='dark')document.documentElement.dataset.theme=t}catch{}
