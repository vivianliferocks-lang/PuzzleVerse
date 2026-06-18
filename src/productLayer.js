(function(){
  const FIREBASE_IMPORTS = {
    app: "https://www.gstatic.com/firebasejs/10.12.5/firebase-app.js",
    auth: "https://www.gstatic.com/firebasejs/10.12.5/firebase-auth.js"
  };

  const STORE_ITEMS = [
    {icon:'🪙',title:'Starter Coins',desc:'Enough to test small custom puzzles and hints.',coins:5000,price:'₹99 / $0.99 prototype'},
    {icon:'🎨',title:'Creator Pack',desc:'Coins for 20–50 piece custom puzzle publishing.',coins:40000,price:'₹499 / $4.99 prototype'},
    {icon:'🏆',title:'Master Puzzle Pack',desc:'Large coin pack for advanced 100+ piece creations.',coins:150000,price:'₹1,499 / $14.99 prototype'},
    {icon:'💡',title:'Hint Bundle',desc:'Production build can sell extra hint bundles.',coins:2500,price:'Bonus: 2,500 coins'},
    {icon:'🧢',title:'Avatar Cosmetics',desc:'Frames, badges, seasonal emojis, and profile effects.',coins:10000,price:'Coming soon'},
    {icon:'🎉',title:'Season Event Pass',desc:'Festival tournaments with leaderboard rewards.',coins:20000,price:'Coming soon'}
  ];

  const LAUNCH_ITEMS = [
    {icon:'🔐',title:'Real Authentication',desc:'Google, Facebook, email login, account linking, password reset, and cloud save.'},
    {icon:'🏁',title:'Verified Leaderboards',desc:'Server-validated solve times, anti-cheat checks, per-puzzle records, and seasonal rankings.'},
    {icon:'🛡️',title:'Upload Moderation',desc:'AI image safety check for nudity/sexual content, violence, hate symbols, and copyrighted abuse risk.'},
    {icon:'🎓',title:'Educational Quality',desc:'Curated images, subject-specific trivia, reviewed facts, source credits, and difficulty progression.'},
    {icon:'🎯',title:'Daily Challenges',desc:'Daily puzzle, streak rewards, daily trivia bonus, and limited-time learning quests.'},
    {icon:'🎧',title:'Game Feel',desc:'Sound effects, soft music, snap animation, celebration effects, haptics for Android, and accessibility settings.'},
    {icon:'💳',title:'Play Store Billing',desc:'Coin packs, hint packs, creator pass, avatar cosmetics, and event pass through Google Play Billing.'},
    {icon:'📜',title:'Policy Readiness',desc:'Privacy policy, terms, data deletion link, Data Safety form, support email, and content reporting.'}
  ];

  function $(id){ return document.getElementById(id); }
  function getState(){ try { return state; } catch(e) { return null; } }
  function saveState(){ try { save(); } catch(e) {} }
  function renderBase(){ try { renderChrome(); } catch(e) {} updateAvatarVisuals(); }

  function updateAvatarVisuals(){
    const s = getState(); if(!s) return;
    const html = s.player.avatarImage ? `<img src="${s.player.avatarImage}" alt="Avatar">` : (s.player.avatar || '🧩');
    if($('avatarBtn')) $('avatarBtn').innerHTML = html;
    if($('profileAvatarBig')) $('profileAvatarBig').innerHTML = html;
    if($('authLabel')) $('authLabel').textContent = s.auth?.provider ? s.auth.provider : (s.auth?.email ? 'Email' : 'Guest');
    if($('profileEmail')) $('profileEmail').textContent = s.auth?.email || 'Guest mode';
  }

  function applyAuthUser(user, providerName){
    const s = getState();
    if(!s || !user) return;
    s.auth = s.auth || {};
    s.auth.mode = 'social';
    s.auth.loggedIn = true;
    s.auth.provider = providerName || 'Social';
    s.auth.email = user.email || '';
    s.player.name = user.displayName || s.player.name || 'Puzzle Creator';
    if(user.photoURL && !s.player.avatarImage) s.player.avatarImage = user.photoURL;
    saveState();
    renderBase();
  }

  async function firebaseSignIn(provider){
    const cfg = window.PV_FIREBASE_CONFIG;
    if(!cfg || !cfg.apiKey){
      showSetupNotice(provider);
      return;
    }
    try {
      const appMod = await import(FIREBASE_IMPORTS.app);
      const authMod = await import(FIREBASE_IMPORTS.auth);
      const app = appMod.initializeApp(cfg);
      const auth = authMod.getAuth(app);
      let authProvider;
      if(provider === 'Google') {
        authProvider = new authMod.GoogleAuthProvider();
      } else {
        authProvider = new authMod.FacebookAuthProvider();
      }
      const result = await authMod.signInWithPopup(auth, authProvider);
      applyAuthUser(result.user, provider);
      const overlay = $('loginOverlay');
      if(overlay) overlay.remove();
      localStorage.setItem('puzzleverse.login.seen','1');
    } catch(err) {
      console.error(err);
      alert(`${provider} login failed. Check Firebase config, enabled provider, authorized domain, and popup permissions.\n\n${err.message || err}`);
    }
  }

  function showSetupNotice(provider){
    alert(`${provider} login button is now added.\n\nTo make it truly connect to real user accounts, configure Firebase Authentication in src/firebaseConfig.js and enable ${provider} sign-in in Firebase Console.\n\nUntil then, use guest/email prototype login for testing.`);
  }

  function showLogin(){
    if(localStorage.getItem('puzzleverse.login.seen')) return;
    const wrap = document.createElement('section');
    wrap.id = 'loginOverlay';
    wrap.className = 'login-screen active';
    wrap.innerHTML = `
      <div class="login-card">
        <img src="assets/branding/puzzleverse-logo.svg?v=pro2" alt="PuzzleVerse" class="login-logo">
        <span class="eyebrow">PuzzleVerse Account</span>
        <h1>Build. Solve. Challenge the world.</h1>
        <p class="small-muted">Save progress, publish puzzles, compete on leaderboards, and join seasonal tournaments.</p>

        <div class="social-login-stack">
          <button id="pvGoogleBtn" class="social-btn google-btn" type="button">
            <span class="social-mark google-mark">G</span>
            Continue with Google
          </button>
          <button id="pvFacebookBtn" class="social-btn facebook-btn" type="button">
            <span class="social-mark facebook-mark">f</span>
            Continue with Facebook
          </button>
        </div>

        <div class="login-divider"><span>or use prototype email</span></div>

        <form id="pvLoginForm" class="login-form">
          <label>Email<input id="pvLoginEmail" type="email" placeholder="you@example.com"></label>
          <label>Display name<input id="pvLoginName" type="text" placeholder="Guest Creator"></label>
          <button class="primary-btn" type="submit">Login / Create Account</button>
        </form>
        <button id="pvGuestBtn" class="ghost-btn wide">Continue as Guest</button>

        <p class="small-muted login-note">Official launch needs privacy policy, account deletion, upload moderation, and server-backed leaderboards.</p>
      </div>`;
    document.body.appendChild(wrap);

    $('pvGoogleBtn').onclick = () => firebaseSignIn('Google');
    $('pvFacebookBtn').onclick = () => firebaseSignIn('Facebook');
    $('pvGuestBtn').onclick = () => { localStorage.setItem('puzzleverse.login.seen','1'); wrap.remove(); };
    $('pvLoginForm').onsubmit = e => {
      e.preventDefault();
      const s = getState();
      if(s){
        s.auth = s.auth || {};
        s.auth.email = $('pvLoginEmail').value.trim();
        s.auth.mode = 'email';
        s.auth.provider = 'Email';
        s.auth.loggedIn = true;
        const name = $('pvLoginName').value.trim();
        if(name) s.player.name = name;
        saveState();
        renderBase();
      }
      localStorage.setItem('puzzleverse.login.seen','1');
      wrap.remove();
    };
  }

  function renderStore(){
    const list = $('storeList'); if(!list) return;
    list.innerHTML = '';
    STORE_ITEMS.forEach(item => {
      const card = document.createElement('article');
      card.className = 'store-card';
      card.innerHTML = `<div class="store-icon">${item.icon}</div><h3>${item.title}</h3><p>${item.desc}</p><div class="store-price">${item.price}</div><button class="primary-btn">Prototype Buy</button>`;
      card.querySelector('button').onclick = () => {
        const s = getState();
        if(s){
          s.player.coins += item.coins;
          saveState();
          renderBase();
        }
        alert(`${item.title}: added ${item.coins.toLocaleString('en-IN')} coins in prototype mode.`);
      };
      list.appendChild(card);
    });

    const lab = document.createElement('section');
    lab.className = 'launch-lab panel';
    lab.innerHTML = `
      <span class="eyebrow">Launch Lab</span>
      <h2>What PuzzleVerse needs before Play Store launch</h2>
      <p>These are the systems that will make the game feel alive, safe, monetizable, and ready for real users.</p>
      <div class="launch-grid">
        ${LAUNCH_ITEMS.map(item => `<article class="launch-card"><div class="launch-icon">${item.icon}</div><h3>${item.title}</h3><p>${item.desc}</p></article>`).join('')}
      </div>
    `;
    list.appendChild(lab);
  }

  function enhanceAvatarDialog(){
    const dlg = $('avatarDialog'); if(!dlg) return;
    const saveBtn = $('saveAvatar'), removeBtn = $('removeAvatarImage');
    if(saveBtn) saveBtn.onclick = () => {
      const s = getState(); if(!s) return;
      s.player.name = $('nameInput').value.trim() || 'Guest Creator';
      s.player.avatar = $('avatarInput').value;
      const file = $('avatarImageInput')?.files?.[0];
      if(file && file.type.startsWith('image/')){
        const reader = new FileReader();
        reader.onload = () => {
          s.player.avatarImage = reader.result;
          saveState(); renderBase(); dlg.close();
        };
        reader.readAsDataURL(file);
      } else {
        saveState(); renderBase(); dlg.close();
      }
    };
    if(removeBtn) removeBtn.onclick = () => {
      const s = getState(); if(!s) return;
      s.player.avatarImage = '';
      saveState(); renderBase();
    };
    if($('openAvatarEditor')) $('openAvatarEditor').onclick = () => $('avatarBtn').click();
  }

  const oldSet = window.setScreen || ((typeof setScreen === 'function') ? setScreen : null);
  if(oldSet){
    window.setScreen = function(id){
      oldSet(id);
      if(id === 'storeScreen') renderStore();
      if(id === 'profileScreen') updateAvatarVisuals();
    };
  }

  setTimeout(() => {
    renderStore();
    enhanceAvatarDialog();
    updateAvatarVisuals();
    showLogin();
  }, 150);
})();