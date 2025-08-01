from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
import requests
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import re

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')  # Add secret key for flash messages

# Configuration
API_KEY = os.getenv('API_KEY')
if not API_KEY:
    raise ValueError("API_KEY not found in environment variables! Please set it in a .env file.")

CLAN_TAG = os.getenv('CLAN_TAG')
# Validate clan tag format
if not re.match(r'^#[A-Z0-9]{5,}$', CLAN_TAG):
    raise ValueError("Invalid CLAN_TAG format. Must start with # followed by uppercase letters/numbers.")

ENCODED_CLAN_TAG = CLAN_TAG.replace('#', '%23')
BASE_URL = 'https://api.clashofclans.com/v1'
CLAN_URL = f"{BASE_URL}/clans/{ENCODED_CLAN_TAG}"
MEMBERS_URL = f"{CLAN_URL}/members"
WARLOG_URL = f"{CLAN_URL}/warlog?limit=10"
CURRENT_WAR_URL = f"{CLAN_URL}/currentwar"
LEAGUE_GROUP_URL = f"{CLAN_URL}/currentwar/leaguegroup"
CAPITAL_RAIDS_URL = f"{CLAN_URL}/capitalraidseasons"

# In-memory cache
cache = {
    'clan_info': {'data': None, 'timestamp': None},
    'members': {'data': None, 'timestamp': None},
    'war_log': {'data': None, 'timestamp': None},
    'current_war': {'data': None, 'timestamp': None},
    'league_group': {'data': None, 'timestamp': None},
    'capital_raids': {'data': None, 'timestamp': None},
    'leagues': {'data': None, 'timestamp': None}
}

# In-memory storage for CWL team selection
cwl_team_selection = {
    'selected_members': [],
    'last_updated': None
}

CACHE_DURATION = 300  # 5 minutes cache

def get_headers():
    return {
        'Authorization': f'Bearer {API_KEY}',
        'Accept': 'application/json'
    }

def is_cache_valid(cache_key):
    if cache[cache_key]['timestamp'] is None:
        return False
    return (datetime.utcnow() - cache[cache_key]['timestamp']) < timedelta(seconds=CACHE_DURATION)

def make_api_request(endpoint):
    try:
        response = requests.get(f"{BASE_URL}{endpoint}", headers=get_headers(), timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            return {'error': 'API rate limit exceeded'}
        return {'error': f'API request failed: {str(e)}'}
    except requests.exceptions.RequestException as e:
        return {'error': f'API request failed: {str(e)}'}

def get_clan_info():
    if is_cache_valid('clan_info'):
        return cache['clan_info']['data']
    
    data = make_api_request(f'/clans/{ENCODED_CLAN_TAG}')
    
    if isinstance(data, dict) and 'error' not in data:
        cache['clan_info']['data'] = data
        cache['clan_info']['timestamp'] = datetime.utcnow()
    
    return data

def get_clan_members():
    if is_cache_valid('members'):
        return cache['members']['data']
    
    data = make_api_request(f'/clans/{ENCODED_CLAN_TAG}/members')
    
    if isinstance(data, dict) and 'error' not in data:
        role_order = {'leader': 1, 'coLeader': 2, 'elder': 3, 'member': 4}
        data['items'] = sorted(data['items'], 
                             key=lambda x: (role_order.get(x['role'], 5), -x['trophies']))
        cache['members']['data'] = data
        cache['members']['timestamp'] = datetime.utcnow()
    
    return data

def get_war_log():
    if is_cache_valid('war_log'):
        return cache['war_log']['data']
    
    data = make_api_request(f'/clans/{ENCODED_CLAN_TAG}/warlog?limit=10')
    
    if isinstance(data, dict) and 'error' not in data:
        cache['war_log']['data'] = data
        cache['war_log']['timestamp'] = datetime.utcnow()
    
    return data

def get_current_war():
    if is_cache_valid('current_war'):
        return cache['current_war']['data']
    
    data = make_api_request(f'/clans/{ENCODED_CLAN_TAG}/currentwar')
    
    if isinstance(data, dict) and 'error' not in data:
        cache['current_war']['data'] = data
        cache['current_war']['timestamp'] = datetime.utcnow()
    
    return data

def get_league_group():
    if is_cache_valid('league_group'):
        return cache['league_group']['data']
    
    data = make_api_request(f'/clans/{ENCODED_CLAN_TAG}/currentwar/leaguegroup')
    
    if isinstance(data, dict) and 'error' not in data:
        cache['league_group']['data'] = data
        cache['league_group']['timestamp'] = datetime.utcnow()
    
    return data

def get_capital_raid_seasons():
    if is_cache_valid('capital_raids'):
        return cache['capital_raids']['data']
    
    data = make_api_request(f'/clans/{ENCODED_CLAN_TAG}/capitalraidseasons')
    
    if isinstance(data, dict) and 'error' not in data:
        cache['capital_raids']['data'] = data
        cache['capital_raids']['timestamp'] = datetime.utcnow()
    
    return data

def get_league_war(war_tag):
    # war_tag should be URL-encoded
    encoded_war_tag = war_tag.replace('#', '%23') if war_tag.startswith('#') else war_tag
    data = make_api_request(f'/clanwarleagues/wars/{encoded_war_tag}')
    return data

def search_clans(params):
    # Construct query string from parameters
    query = '&'.join(f"{key}={value}" for key, value in params.items() if value)
    data = make_api_request(f'/clans?{query}' if query else '/clans')
    return data

def get_player(player_tag):
    encoded_player_tag = player_tag.replace('#', '%23') if player_tag.startswith('#') else player_tag
    data = make_api_request(f'/players/{encoded_player_tag}')
    return data

def get_leagues():
    if is_cache_valid('leagues'):
        return cache['leagues']['data']
    
    data = make_api_request('/leagues')
    
    if isinstance(data, dict) and 'error' not in data:
        cache['leagues']['data'] = data
        cache['leagues']['timestamp'] = datetime.utcnow()
    
    return data

@app.route('/')
def home():
    clan_info = get_clan_info()
    members = get_clan_members()
    
    if isinstance(clan_info, dict) and 'error' in clan_info:
        return render_template('error.html', error=clan_info['error'])
    if isinstance(members, dict) and 'error' in members:
        return render_template('error.html', error=members['error'])
    
    return render_template('index.html', 
                         clan_info=clan_info, 
                         members=members.get('items', []) if members else [])

@app.route('/war')
def war_performance():
    war_log = get_war_log()
    
    if isinstance(war_log, dict) and 'error' in war_log:
        return render_template('error.html', error=war_log['error'])
    
    return render_template('war.html', war_log=war_log.get('items', []) if war_log else [])

@app.route('/current-war')
def current_war():
    current_war = get_current_war()
    
    if isinstance(current_war, dict) and 'error' in current_war:
        return render_template('error.html', error=current_war['error'])
    
    return render_template('current_war.html', current_war=current_war if current_war else {})

@app.route('/league-group')
def league_group():
    league_group = get_league_group()
    
    if isinstance(league_group, dict) and 'error' in league_group:
        return render_template('error.html', error=league_group['error'])
    
    return render_template('league_group.html', league_group=league_group if league_group else {})

@app.route('/capital-raids')
def capital_raids():
    capital_raids = get_capital_raid_seasons()
    
    if isinstance(capital_raids, dict) and 'error' in capital_raids:
        return render_template('error.html', error=capital_raids['error'])
    
    return render_template('capital_raids.html', capital_raids=capital_raids.get('items', []) if capital_raids else [])

@app.route('/cwl-team-selection')
def cwl_team_selection_page():
    members = get_clan_members()
    
    if isinstance(members, dict) and 'error' in members:
        return render_template('error.html', error=members['error'])
    
    # Get current selected members
    selected_tags = [member['tag'] for member in cwl_team_selection['selected_members']]
    
    # Add selection status to members
    all_members = members.get('items', []) if members else []
    for member in all_members:
        member['selected'] = member['tag'] in selected_tags
    
    return render_template('cwl_team_selection.html', 
                         members=all_members,
                         selected_count=len(cwl_team_selection['selected_members']),
                         last_updated=cwl_team_selection['last_updated'])

@app.route('/cwl-team-selection', methods=['POST'])
def update_cwl_team_selection():
    selected_member_tags = request.form.getlist('selected_members')
    
    # Get all members to find selected ones
    members = get_clan_members()
    if isinstance(members, dict) and 'error' in members:
        flash('Error fetching members: ' + members['error'], 'error')
        return redirect(url_for('cwl_team_selection_page'))
    
    all_members = members.get('items', []) if members else []
    
    # Update selected members
    cwl_team_selection['selected_members'] = [
        member for member in all_members 
        if member['tag'] in selected_member_tags
    ]
    cwl_team_selection['last_updated'] = datetime.utcnow()
    
    flash(f'CWL team updated! {len(cwl_team_selection["selected_members"])} members selected.', 'success')
    return redirect(url_for('cwl_team_selection_page'))

@app.route('/cwl-roster')
def cwl_roster():
    # Show the final selected CWL roster
    selected_members = cwl_team_selection['selected_members']
    
    # Sort by role and trophies
    role_order = {'leader': 1, 'coLeader': 2, 'elder': 3, 'member': 4}
    selected_members_sorted = sorted(selected_members, 
                                   key=lambda x: (role_order.get(x['role'], 5), -x['trophies']))
    
    return render_template('cwl_roster.html', 
                         selected_members=selected_members_sorted,
                         total_selected=len(selected_members),
                         last_updated=cwl_team_selection['last_updated'])

@app.route('/search-clans', methods=['GET'])
def search_clans_route():
    params = {
        'name': request.args.get('name', ''),
        'minMembers': request.args.get('minMembers', ''),
        'minClanLevel': request.args.get('minClanLevel', ''),
        'warFrequency': request.args.get('warFrequency', '')
    }
    params = {k: v for k, v in params.items() if v}  # Remove empty params
    try:
        response = requests.get(f"{BASE_URL}/clans", headers=get_headers(), params=params)
        response.raise_for_status()
        clans = response.json().get('items', [])
        return render_template('search_clans.html', clans=clans)
    except requests.RequestException:
        return render_template('error.html', error="Failed to fetch clans")
        
@app.route('/player/<player_tag>')
def player(player_tag):
    player_info = get_player(player_tag)
    
    if isinstance(player_info, dict) and 'error' in player_info:
        return render_template('error.html', error=player_info['error'])
    
    return render_template('player.html', player=player_info if player_info else {})

@app.route('/leagues')
def leagues():
    leagues = get_leagues()
    
    if isinstance(leagues, dict) and 'error' in leagues:
        return render_template('error.html', error=leagues['error'])
    
    return render_template('leagues.html', leagues=leagues.get('items', []) if leagues else [])

@app.route('/api/league-war/<war_tag>')
def league_war_api(war_tag):
    war = get_league_war(war_tag)
    
    if isinstance(war, dict) and 'error' in war:
        return jsonify({'error': war['error']})
    
    return jsonify(war if war else {})

@app.route('/api/cwl-team')
def api_cwl_team():
    """API endpoint to get current CWL team selection"""
    return jsonify({
        'selected_members': cwl_team_selection['selected_members'],
        'count': len(cwl_team_selection['selected_members']),
        'last_updated': cwl_team_selection['last_updated'].isoformat() if cwl_team_selection['last_updated'] else None
    })

@app.route('/api/war-stats')
def war_stats_api():
    war_log = get_war_log()
    if isinstance(war_log, dict) and 'error' in war_log:
        return jsonify({'error': war_log['error']})
    
    wars = war_log.get('items', [])
    
    wins = sum(1 for war in wars if war['result'] == 'win')
    losses = sum(1 for war in wars if war['result'] == 'lose')
    draws = sum(1 for war in wars if war['result'] == 'tie')
    
    our_stars = []
    our_destruction = []
    opponent_destruction = []
    war_results = []
    
    for war in wars:
        our_stars.append(war['clan']['stars'])
        our_destruction.append(war['clan']['destructionPercentage'])
        opponent_destruction.append(war['opponent']['destructionPercentage'])
        war_results.append({
            'opponent': war['opponent']['name'],
            'result': war['result'],
            'our_stars': war['clan']['stars'],
            'opponent_stars': war['opponent']['stars'],
            'our_destruction': war['clan']['destructionPercentage'],
            'opponent_destruction': war['opponent']['destructionPercentage']
        })
    
    return jsonify({
        'win_loss': {'wins': wins, 'losses': losses, 'draws': draws},
        'stars_trend': our_stars,
        'destruction_comparison': {
            'our_destruction': our_destruction,
            'opponent_destruction': opponent_destruction
        },
        'war_results': war_results
    })

@app.route('/api/top-players')
def top_players():
    members = get_clan_members()
    if isinstance(members, dict) and 'error' in members:
        return jsonify({'error': members['error']})
    
    players = members.get('items', [])
    
    top_donations = sorted(players, key=lambda x: x['donations'], reverse=True)[:10]
    top_trophies = sorted(players, key=lambda x: x['trophies'], reverse=True)[:10]
    top_received = sorted(players, key=lambda x: x['donationsReceived'], reverse=True)[:10]
    
    return jsonify({
        'top_donations': top_donations,
        'top_trophies': top_trophies,
        'top_received': top_received
    })

if __name__ == '__main__':
    if os.getenv('FLASK_ENV') == 'production':
        app.run(debug=False)
    else:
        app.run(debug=True)