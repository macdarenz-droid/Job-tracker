// Load the saved theme before the page paints. Dark is the default.
try{const t=localStorage.getItem('tracker-theme');if(t==='light'||t==='dark')document.documentElement.dataset.theme=t}catch{}
