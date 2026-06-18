# PuzzleVerse Social Login + Launch Readiness Pack V1

This is a direct replacement pack.

## What this adds

1. Login popup now has:
   - Continue with Google
   - Continue with Facebook
   - prototype email login
   - guest mode

2. Adds:
   - src/firebaseConfig.js

By default Firebase config is null, so Google/Facebook buttons show a setup message.
After you configure Firebase, the buttons can connect to real Google/Facebook accounts.

3. Store tab now includes Launch Lab:
   - real auth
   - verified leaderboards
   - upload moderation
   - educational QA
   - daily challenges
   - game feel
   - Google Play Billing
   - policy readiness

## Replace these files in D:\Games\PuzzleVerse\

- index.html
- styles.css
- src/productLayer.js
- src/firebaseConfig.js

## Test

cd D:\Games\PuzzleVerse
python -m http.server 8000

Open:
http://localhost:8000

Hard refresh:
Ctrl + Shift + R

## Real Google/Facebook login setup

Edit:
src/firebaseConfig.js

Add your Firebase web app config, then enable Google and Facebook sign-in providers in Firebase Authentication.

For Facebook sign-in you will also need a Meta/Facebook app ID and app secret added in Firebase Console.
