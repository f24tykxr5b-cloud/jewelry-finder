# פריסה לאינטרנט — Streamlit Community Cloud (חינמי)

## שלב 1 — GitHub (5 דקות)
1. כנס ל-github.com וצור חשבון חינמי אם אין לך
2. לחץ **New repository** → שם: `jewelry-platforms`
3. סמן **Public** → לחץ **Create**
4. בטרמינל, תוך כדי תיקיית הפרויקט:
   ```bash
   git init
   git add .
   git commit -m "first commit"
   git remote add origin https://github.com/<שם-משתמש>/jewelry-platforms.git
   git push -u origin main
   ```

## שלב 2 — Streamlit Cloud (3 דקות)
1. כנס ל-**share.streamlit.io** → **Sign in with GitHub**
2. לחץ **New app**
3. בחר את הריפו `jewelry-platforms`
4. Branch: `main` · Main file: `app.py`
5. לחץ **Deploy** — תוך ~2 דקות יש לך URL כמו:
   `https://jewelry-platforms.streamlit.app`

## תוצאה
- **גישה מכל מקום** — מחשב, טלפון, טאבלט
- **עדכונים אוטומטיים** — כל push לגיטהאב → האפליקציה מתעדכנת
- **חינמי לחלוטין**

## עדכון רשימת הפלטפורמות
ערוך את `platforms_data.py` → שמור → `git push` → האפליקציה מתעדכנת תוך דקה.
