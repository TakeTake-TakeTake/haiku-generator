from flask import Flask, render_template, request, redirect, url_for, session
from haiku_data import season_words_by_season, themes_by_emotion
from openai import OpenAI
import random
import os
import re
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

app = Flask(__name__)
app.secret_key = 'your_secret_key'

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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/select_keywords', methods=['POST'])
def select_keywords():
    season = request.form.get('season')
    emotion = request.form.get('emotion')
    session['season'] = season
    session['emotion'] = emotion
    session['season_words'] = random.sample(season_words_by_season.get(season, []), 5)
    session['themes'] = random.sample(themes_by_emotion.get(emotion, []), 5)
    return redirect(url_for('show_keywords'))

@app.route('/show_keywords')
def show_keywords():
    season = session.get('season')
    emotion = session.get('emotion')
    season_words = session.get('season_words') or random.sample(season_words_by_season.get(season, []), 5)
    themes = session.get('themes') or random.sample(themes_by_emotion.get(emotion, []), 5)
    session['season_words'] = season_words
    session['themes'] = themes
    return render_template('keyword_select.html', season_words=season_words, themes=themes, season=season, emotion=emotion)

@app.route('/refresh_season_words', methods=['POST'])
def refresh_season_words():
    season = session.get('season')
    season_words = random.sample(season_words_by_season.get(season, []), 5)
    session['season_words'] = season_words
    return redirect(url_for('show_keywords'))

@app.route('/refresh_themes', methods=['POST'])
def refresh_themes():
    emotion = session.get('emotion')
    themes = random.sample(themes_by_emotion.get(emotion, []), 5)
    session['themes'] = themes
    return redirect(url_for('show_keywords'))

@app.route('/generate_haiku', methods=['POST'])
def generate_haiku():
    selected_season_word = request.form.get('selected_season_word')
    selected_theme = request.form.get('selected_theme')
    if not selected_season_word or not selected_theme:
        return "季語とテーマを選択してください。"

    prompt = f"季語「{selected_season_word}」とテーマ「{selected_theme}」を含む俳句を1つ生成してください。"
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "あなたは俳句の達人です。"},
                {"role": "user", "content": prompt}
            ]
        )
        haiku = response.choices[0].message.content.strip()
        haiku_furigana, haiku_reading = generate_furigana_and_reading(haiku)
    except Exception as e:
        haiku = f"エラーが発生しました: {str(e)}"
        haiku_furigana = haiku
        haiku_reading = ""

    return render_template('haiku_result.html', haiku=haiku, haiku_furigana=haiku_furigana, haiku_reading=haiku_reading, season=session.get('season'), emotion=session.get('emotion'), season_word=selected_season_word, theme=selected_theme)

@app.route('/revise_haiku', methods=['POST'])
def revise_haiku():
    haiku = request.form.get('haiku')
    feedback = request.form.get('feedback')
    selected_season_word = request.form.get('season_word')
    selected_theme = request.form.get('theme')

    if not feedback:
        haiku_furigana, haiku_reading = generate_furigana_and_reading(haiku)
        return render_template('haiku_result.html', haiku=haiku, haiku_furigana=haiku_furigana, haiku_reading=haiku_reading, season=session.get('season'), emotion=session.get('emotion'), season_word=selected_season_word, theme=selected_theme)

    prompt = f"この俳句「{haiku}」に対して、次のフィードバックを受けました：「{feedback}」。フィードバックを反映して俳句を改善してください。"
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "あなたは俳句の達人です。"},
                {"role": "user", "content": prompt}
            ]
        )
        revised_haiku = response.choices[0].message.content.strip()
        revised_furigana, revised_reading = generate_furigana_and_reading(revised_haiku)
    except Exception as e:
        revised_haiku = f"エラーが発生しました: {str(e)}"
        revised_furigana = revised_haiku
        revised_reading = ""

    return render_template('haiku_result.html', haiku=revised_haiku, haiku_furigana=revised_furigana, haiku_reading=revised_reading, season=session.get('season'), emotion=session.get('emotion'), season_word=selected_season_word, theme=selected_theme)

@app.route('/feedback', methods=['POST'])
def feedback():
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
