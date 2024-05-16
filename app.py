from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import random
import json
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Teksta ielāde no JSON faila
def load_texts():
    with open('texts.json', 'r', encoding='utf-8') as file:
        return json.load(file)

texts = load_texts()

# Datubāzes inicializācija
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS players
                 (id INTEGER PRIMARY KEY, username TEXT, password TEXT, level INTEGER, xp INTEGER, games_played INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS games
                 (id INTEGER PRIMARY KEY, player_id INTEGER, xp_earned INTEGER, result TEXT, FOREIGN KEY(player_id) REFERENCES players(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS levels
                 (level INTEGER PRIMARY KEY, xp_required INTEGER)''')
    conn.commit()
    conn.close()

# Izveido līmeņu tabulu, ja tā neeksistē
def init_levels():
    levels = {
        1: 0,
        2: 100,
        3: 250,
        4: 450,
        5: 700,
        6: 1000,
        7: 1350,
        8: 1750,
        9: 2200,
        10: 2700
    }
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    for level, xp_required in levels.items():
        c.execute('INSERT OR IGNORE INTO levels (level, xp_required) VALUES (?, ?)', (level, xp_required))
    conn.commit()
    conn.close()

# Lietotāja reģistrācijas skats
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('INSERT INTO players (username, password, level, xp, games_played) VALUES (?, ?, ?, ?, ?)', (username, password, 1, 0, 0))
        conn.commit()
        conn.close()
        return redirect(url_for('login'))

    return render_template('register.html', texts=texts)

# Lietotāja pieslēgšanās skats
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('SELECT id, password FROM players WHERE username = ?', (username,))
        user = c.fetchone()
        conn.close()

        if user and check_password_hash(user[1], password):
            session['user_id'] = user[0]
            return redirect(url_for('dashboard'))

    return render_template('login.html', texts=texts)

# Lietotāja izrakstīšanās skats
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

# Lietotāja informācijas skats
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT username, level, xp, games_played FROM players WHERE id = ?', (user_id,))
    user = c.fetchone()
    if not user:
        return redirect(url_for('login'))  # Ja lietotājs netika atrasts

    next_level = user[1] + 1
    c.execute('SELECT xp_required FROM levels WHERE level = ?', (next_level,))
    next_level_xp = c.fetchone()
    if not next_level_xp:
        next_level_xp = [0]  # Ja nākamais līmenis netika atrasts
    xp_to_next_level = max(0, next_level_xp[0] - user[2])
    conn.close()

    return render_template('dashboard.html', user=user, xp_to_next_level=xp_to_next_level, texts=texts)

# Spēles sākšanas skats
@app.route('/start_game')
def start_game():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    session['health'] = 100
    session['battle_points'] = 0
    return redirect(url_for('game'))

# Spēles skats
@app.route('/game', methods=['GET', 'POST'])
def game():
    if 'user_id' not in session or 'health' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        action = request.form['action']
        if action == 'fight':
            damage = random.randint(12, 26)
            points = random.randint(10, 30)
            session['health'] -= damage
            session['battle_points'] += points

            if session['health'] <= 0:
                return end_game('lost')

        elif action == 'flee':
            return end_game('fled')

    return render_template('game.html', health=session['health'], battle_points=session['battle_points'], texts=texts)

def end_game(result):
    user_id = session['user_id']
    battle_points = session['battle_points']
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('UPDATE players SET xp = xp + ?, games_played = games_played + 1 WHERE id = ?', (battle_points, user_id))
    conn.commit()
    conn.close()
    
    # Atjaunina spēlētāja līmeni
    update_player_level(user_id)
    
    session.pop('health', None)
    session.pop('battle_points', None)
    return redirect(url_for('dashboard'))


# Lietotāja spēļu saraksts
@app.route('/games')
def games():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT id, xp_earned, result FROM games WHERE player_id = ?', (user_id,))
    games = c.fetchall()
    conn.close()

    return render_template('games.html', games=games, texts=texts)

def update_player_level(player_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT xp FROM players WHERE id = ?', (player_id,))
    xp = c.fetchone()[0]

    # Atrodiet maksimālo līmeni, kuru spēlētājs var sasniegt ar esošajiem pieredzes punktiem
    c.execute('SELECT level FROM levels WHERE xp_required <= ? ORDER BY level DESC LIMIT 1', (xp,))
    new_level = c.fetchone()[0]
    
    c.execute('UPDATE players SET level = ? WHERE id = ?', (new_level, player_id))
    conn.commit()
    conn.close()


# Sākumskats
@app.route('/')
def index():
    return redirect(url_for('login'))

if __name__ == '__main__':
    init_db()
    init_levels()
    app.run(debug=True)
