from flask import Flask, render_template, request, redirect, url_for, session
from haiku_data import season_words_by_season, themes_by_emotion
from openai import OpenAI
import random

# OpenAI API設定
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

app = Flask(__name__)
app.secret_key = 'your_secret_key'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/select_keywords', methods=['POST'])
def select_keywords():
    season = request.form.get('season')
    emotion = request.form.get('emotion')
    session['season'] = season
    session['emotion'] = emotion
    return redirect(url_for('show_keywords'))

@app.route('/show_keywords')
def show_keywords():
    season = session.get('season')
    emotion = session.get('emotion')

    season_words = random.sample(season_words_by_season.get(season, []), 5)
    themes = random.sample(themes_by_emotion.get(emotion, []), 5)

    session['season_words'] = season_words
    session['themes'] = themes

    return render_template('keyword_select.html',
                           season_words=season_words,
                           themes=themes,
                           season=season,
                           emotion=emotion)

@app.route('/refresh_keywords', methods=['POST'])
def refresh_keywords():
    return redirect(url_for('show_keywords'))

def generate_furigana_and_reading(text):
    prompt = f"""
以下の俳句を5・7・5の3句に分けて「漢字/ふりがな」形式で出力し、全文のひらがな読みも出力してください。

俳句：
{text}

出力例：
句1: 春霞/はるがすみ
句2: 山/やま の/の 向こう/むこう に/に
句3: 光/ひかり の/の 道/みち
読み: はるがすみ やまのむこうに ひかりのみち
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "あなたはふりがな変換と読み変換を行う日本語アシスタントです。"},
            {"role": "user", "content": prompt}
        ]
    )

    ruby_text = ""
    reading_text = ""
    lines = response.choices[0].message.content.strip().split("\n")

    for line in lines:
        if line.startswith("句"):
            _, content = line.split(":", 1)
            parts = []
            for pair in content.strip().split():
                if "/" in pair:
                    k, r = pair.split("/")
                    parts.append(f"<ruby>{k}<rt>{r}</rt></ruby>" if k != r else k)
                else:
                    parts.append(pair)
            ruby_text += f"<span class='ku'>{' '.join(parts)}</span> "
        elif line.startswith("読み:"):
            reading_text = line.replace("読み:", "").strip()

    return ruby_text.strip(), reading_text.strip()

def is_valid_feedback(feedback):
    prompt = f"""
以下のコメントが、俳句に対して具体的な改善・変更の意図を含む指示かどうかを判定してください。単に感想・無意味・ノイズ（例：あああ、いいね等）であれば「NO」と答え、明確な指示や改善要望であれば「YES」と答えてください。

コメント: "{feedback}"

出力はYESまたはNOのみとしてください。
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )
    return "YES" in response.choices[0].message.content.upper()

@app.route('/generate_haiku', methods=['POST'])
def generate_haiku():
    season = session.get('season')
    emotion = session.get('emotion')
    season_word = request.form.get('selected_season_word')
    theme = request.form.get('selected_theme')

    prompt = f"""
季節「{season}」、季語「{season_word}」、感情「{emotion}」、テーマ「{theme}」をもとに、5・7・5の俳句を生成してください。
俳句のみを出力してください。
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )

    haiku = response.choices[0].message.content.strip()
    haiku_furigana, haiku_reading = generate_furigana_and_reading(haiku)

    session['season_word'] = season_word
    session['theme'] = theme
    session['haiku'] = haiku
    session['haiku_furigana'] = haiku_furigana
    session['haiku_reading'] = haiku_reading

    return render_template('haiku_result.html',
                           season=season,
                           emotion=emotion,
                           season_word=season_word,
                           theme=theme,
                           haiku=haiku,
                           haiku_furigana=haiku_furigana or "",
                           haiku_reading=haiku_reading or "")

@app.route('/revise_haiku', methods=['POST'])
def revise_haiku():
    feedback = request.form.get('feedback')
    season = session.get('season')
    emotion = session.get('emotion')
    season_word = session.get('season_word')
    theme = session.get('theme')

    if not is_valid_feedback(feedback):
        return render_template('haiku_result.html',
                               season=season,
                               emotion=emotion,
                               season_word=season_word,
                               theme=theme,
                               haiku=session['haiku'],
                               haiku_furigana=session['haiku_furigana'],
                               haiku_reading=session['haiku_reading'])

    prompt = f"""
以下の条件に基づいて、俳句を再生成してください：
- 季節: {season}
- 感情: {emotion}
- 季語: {season_word}
- テーマ: {theme}
- フィードバックコメント: {feedback}

5・7・5の俳句形式を保ちつつ、コメントを反映した改善版を出力してください。
俳句のみを出力してください。
"""
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )

    new_haiku = response.choices[0].message.content.strip()
    new_furigana, new_reading = generate_furigana_and_reading(new_haiku)

    session['haiku'] = new_haiku
    session['haiku_furigana'] = new_furigana
    session['haiku_reading'] = new_reading

    return render_template('haiku_result.html',
                           season=season,
                           emotion=emotion,
                           season_word=season_word,
                           theme=theme,
                           haiku=new_haiku,
                           haiku_furigana=new_furigana,
                           haiku_reading=new_reading)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

# --- HTMLファイルはCanvas外で管理中 ---
