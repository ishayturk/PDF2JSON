
# Project: PDF2JSON | מתווך בקליק | main.py
import streamlit as st
import pdfplumber
import google.generativeai as genai
import json
import re

st.set_page_config(page_title="PDF2JSON | מתווך בקליק", layout="centered")
st.markdown("<style>* { direction: rtl; text-align: right; }</style>", unsafe_allow_html=True)

st.title("🔄 המרת בחינה ל-JSON")
st.markdown("העלה קובץ בחינה וקובץ תשובות — המערכת תייצר קובץ JSON מוכן לשימוש.")

def extract_text(pdf_file):
    text = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
    return text.strip()

def convert_with_gemini(exam_text, answers_text):
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-2.0-flash')
    prompt = f"""להלן טקסט של בחינה רישיון מתווכים וקובץ תשובות.
המשימה: הפק JSON תקני בדיוק במבנה הבא:

{{
  "exam_name": "שם הבחינה",
  "questions": {{
    "1": {{
      "text": "טקסט השאלה המלא",
      "options": {{
        "א": "טקסט תשובה א",
        "ב": "טקסט תשובה ב",
        "ג": "טקסט תשובה ג",
        "ד": "טקסט תשובה ד"
      }},
      "correct_label": "א"
    }},
    ...25 שאלות...
  }}
}}

חוקים:
- בדיוק 25 שאלות
- כל שאלה עם בדיוק 4 תשובות: א, ב, ג, ד
- correct_label חייב להיות אחד מ: א, ב, ג, ד
- שמור על הטקסט המלא של כל שאלה ותשובה
- החזר JSON בלבד, ללא הסברים נוספים

=== טקסט הבחינה ===
{exam_text}

=== טקסט התשובות ===
{answers_text}
"""
    for attempt in range(3):
        try:
            response = model.generate_content(prompt)
            res_text = response.text.replace('```json', '').replace('```', '').strip()
            match = re.search(r'\{.*\}', res_text, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception as e:
            if attempt == 2:
                st.error(f"שגיאה בהמרה: {e}")
    return None

def validate_json(data):
    errors = []
    warnings = []

    # בדיקת מבנה בסיסי
    if "questions" not in data:
        errors.append("חסר שדה 'questions'")
        return errors, warnings
    if "exam_name" not in data:
        warnings.append("חסר שדה 'exam_name'")

    questions = data["questions"]

    # בדיקת מספר שאלות
    if len(questions) != 25:
        errors.append(f"מספר שאלות: {len(questions)} במקום 25")

    valid_labels = {"א", "ב", "ג", "ד"}

    for n in range(1, 26):
        key = str(n)
        if key not in questions:
            errors.append(f"שאלה {n} חסרה")
            continue
        q = questions[key]

        # בדיקת שדה text
        if "text" not in q or not q["text"].strip():
            errors.append(f"שאלה {n}: טקסט ריק")

        # בדיקת options
        if "options" not in q:
            errors.append(f"שאלה {n}: חסר שדה options")
        else:
            opts = q["options"]
            if len(opts) != 4:
                errors.append(f"שאלה {n}: {len(opts)} תשובות במקום 4")
            for lbl in valid_labels:
                if lbl not in opts:
                    errors.append(f"שאלה {n}: חסרה תשובה '{lbl}'")
                elif not opts[lbl].strip():
                    errors.append(f"שאלה {n}: תשובה '{lbl}' ריקה")

        # בדיקת correct_label
        if "correct_label" not in q:
            errors.append(f"שאלה {n}: חסר correct_label")
        elif q["correct_label"] not in valid_labels:
            errors.append(f"שאלה {n}: correct_label לא תקין — '{q['correct_label']}'")

        # בדיקת עברית
        if "text" in q and q["text"]:
            hebrew_chars = sum(1 for c in q["text"] if '\u05d0' <= c <= '\u05ea')
            if hebrew_chars < 5:
                warnings.append(f"שאלה {n}: ייתכן שהטקסט אינו עברי תקין")

    return errors, warnings


# ===== ממשק =====
exam_file = st.file_uploader("📄 קובץ בחינה (PDF)", type=["pdf"])
answers_file = st.file_uploader("📋 קובץ תשובות (PDF)", type=["pdf"])

if exam_file and answers_file:
    if st.button("🔄 המר ל-JSON"):
        with st.spinner("מחלץ טקסט מהקבצים..."):
            exam_text = extract_text(exam_file)
            answers_text = extract_text(answers_file)

        if not exam_text:
            st.error("לא ניתן לחלץ טקסט מקובץ הבחינה.")
            st.stop()
        if not answers_text:
            st.error("לא ניתן לחלץ טקסט מקובץ התשובות.")
            st.stop()

        with st.spinner("ממיר עם Gemini..."):
            result = convert_with_gemini(exam_text, answers_text)

        if not result:
            st.error("ההמרה נכשלה. אנא נסה שוב.")
            st.stop()

        # בדיקת איכות
        errors, warnings = validate_json(result)

        st.markdown("---")
        st.subheader("📊 דוח בדיקה")

        if errors:
            st.error(f"נמצאו {len(errors)} שגיאות:")
            for e in errors:
                st.markdown(f"- ❌ {e}")
        else:
            st.success("✅ הקובץ נבדק ונמצא תקין")

        if warnings:
            st.warning(f"אזהרות ({len(warnings)}):")
            for w in warnings:
                st.markdown(f"- ⚠️ {w}")

        if not errors:
            json_str = json.dumps(result, ensure_ascii=False, indent=2)
            raw_name = exam_file.name  # e.g. test_aug1_v1_2024.pdf
            base = raw_name.rsplit(".", 1)[0]  # remove extension
            output_name = re.sub(r'(?i)test', 'exam', base) + ".json"
            st.download_button(
                label="⬇️ הורד JSON",
                data=json_str.encode("utf-8"),
                file_name=output_name,
                mime="application/json"
            )

        with st.expander("תצוגה מקדימה של ה-JSON"):
            st.json(result)
# סוף קובץ
