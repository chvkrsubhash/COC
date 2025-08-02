import os
import re
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')  # Required for flash messages

# Configuration
API_KEY = os.getenv('API_KEY')
CLAN_TAG = os.getenv('CLAN_TAG', '#2G9C9QCL2') # Use environment variable for clan tag
CLAN_TAG = CLAN_TAG.replace('O', '0') # Clean up common user input errors
ENCODED_CLAN_TAG = CLAN_TAG.replace('#', '%23')
BASE_URL = 'https://api.clashofclans.com/v1'

if not API_KEY:
    logging.error("API_KEY not found in environment variables. API calls will fail.")
if not re.match(r'^#[A-Z0-9]{5,}$', CLAN_TAG):
    logging.error("Invalid CLAN_TAG format. Must start with # followed by uppercase letters/numbers.")

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
    if not API_KEY:
        return {'error': 'API key is not configured.'}
    
    try:
        url = f"{BASE_URL}{endpoint}"
        logging.info(f"Making API request to: {url}")
        response = requests.get(url, headers=get_headers(), timeout=20)
        response.raise_for_status()
        data = response.json()
        logging.info(f"API response received for {endpoint}")
        return data
    except requests.exceptions.HTTPError as e:
        logging.error(f"HTTP error for {endpoint}: {str(e)}")
        if e.response.status_code == 403:
            return {'error': f'API request failed: 403 Forbidden. This is likely an IP address issue. See README.md for instructions on how to register your server IP.'}
        elif e.response.status_code == 429:
            return {'error': 'API rate limit exceeded'}
        return {'error': f'API request failed: {e.response.status_code} - {e.response.text}'}
    except requests.exceptions.RequestException as e:
        logging.error(f"Request error for {endpoint}: {str(e)}")
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
    
    data = make_api_request(f'/clans/{ENCODED_CLAN_TAG}/warlog?limit=20')
    
    if isinstance(data, dict) and 'error' not in data:
        cache['war_log']['data'] = data
        cache['war_log']['timestamp'] = datetime.utcnow()
    
    return data

def get_current_war():
    if is_cache_valid('current_war'):
        return cache['current_war']['data']
    
    data = make_api_request(f'/clans/{ENCODED_CLAN_TAG}/currentwar')
    
    if isinstance(data, dict) and 'error' not in data:
        if 'clan' in data and isinstance(data['clan'], dict):
            if 'attacks' not in data['clan'] or not isinstance(data['clan']['attacks'], list):
                data['clan']['attacks'] = []
        if 'opponent' in data and isinstance(data['opponent'], dict):
            if 'attacks' not in data['opponent'] or not isinstance(data['opponent']['attacks'], list):
                data['opponent']['attacks'] = []
        
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
    encoded_war_tag = war_tag.replace('#', '%23') if war_tag.startswith('#') else war_tag
    data = make_api_request(f'/clanwarleagues/wars/{encoded_war_tag}')
    return data

def search_clans(params):
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
    
    selected_tags = [member['tag'] for member in cwl_team_selection['selected_members']]
    
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
    
    members = get_clan_members()
    if isinstance(members, dict) and 'error' in members:
        flash('Error fetching members: ' + members['error'], 'error')
        return redirect(url_for('cwl_team_selection_page'))
    
    all_members = members.get('items', []) if members else []
    
    cwl_team_selection['selected_members'] = [
        member for member in all_members 
        if member['tag'] in selected_member_tags
    ]
    cwl_team_selection['last_updated'] = datetime.utcnow()
    
    flash(f'CWL team updated! {len(cwl_team_selection["selected_members"])} members selected.', 'success')
    return redirect(url_for('cwl_team_selection_page'))

@app.route('/cwl-roster')
def cwl_roster():
    selected_members = cwl_team_selection['selected_members']
    
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
    params = {k: v for k, v in params.items() if v}
    try:
        response = requests.get(f"{BASE_URL}/clans", headers=get_headers(), params=params, timeout=20)
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
    
    top_donations = sorted(players, key=lambda x: x['donations'], reverse=True)[:20]
    top_trophies = sorted(players, key=lambda x: x['trophies'], reverse=True)[:20]
    top_received = sorted(players, key=lambda x: x['donationsReceived'], reverse=True)[:20]
    
    return jsonify({
        'top_donations': top_donations,
        'top_trophies': top_trophies,
        'top_received': top_received
    })

@app.route('/register_ip', methods=['GET'])
def register_ip():
    """
    A utility endpoint to register the current server's IP address with the
    Clash of Clans API key. This should be run ONCE after deployment.
    """
    if not API_KEY:
        return jsonify({'error': 'API key not configured.'}), 400

    try:
        # Get the public IP of the Vercel server
        ip_response = requests.get('https://api.ipify.org?format=json', timeout=10)
        ip_response.raise_for_status()
        current_ip = ip_response.json()['ip']
        logging.info(f"Detected server IP: {current_ip}")
    except requests.RequestException:
        return jsonify({'error': 'Could not get server IP address.'}), 500
    
    # Send a request to the CoC API to register this IP
    try:
        # This API is not public and would require a specific POST request
        # with the private API token to update the key.
        # This is a conceptual example. The actual implementation would
        # involve a separate API for the CoC developer portal.
        # The correct way is to log in to the developer portal and add the IP.
        
        # For demonstration, let's just show the IP.
        flash(f"Your server's public IP address is: {current_ip}. Please add this IP to your API key on the Supercell Developer Portal manually.", 'info')
        return redirect(url_for('home'))

    except requests.RequestException as e:
        error_message = f"Failed to register IP with CoC API. Please do it manually. Error: {str(e)}"
        logging.error(error_message)
        return jsonify({'error': error_message}), 500

    
if __name__ == '__main__':
    if os.getenv('FLASK_ENV') == 'production':
        app.run(debug=False)
    else:
        app.run(debug=True)
