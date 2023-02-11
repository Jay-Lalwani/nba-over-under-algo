import pandas as pd
import numpy as np
from pandas import json_normalize
import urllib.request
import json
import pickle
import time
import json
from tqdm import tqdm

# CAUTION, BEFORE USE DOWNLOAD "projections.json" FROM https://api.prizepicks.com/projections

def load(filename):
    infile = open(filename, 'rb')
    obj = pickle.load(infile)
    infile.close()
    return obj

def save(s, filename):
    outfile = open(filename, 'wb')
    pickle.dump(s, outfile)
    outfile.close()

def getPicks():
    # params = (
    #     ('league_id', '7'),
    #     ('per_page', '250'),
    #     ('single_stat', 'true'),
    # )
    # headers = {
    # 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36'
    # }
    
    # session = requests.Session()
    # response = session.get('https://api.prizepicks.com/projections', data=params, headers=headers)
    # data = response.json()
    
    data = json.load(open('projections.json', 'r'))
    
    players_df = json_normalize(data['included'])
    players_df = players_df[players_df['type'] == 'new_player']

    projections = []
    stat_types = ['Points', 'Rebounds', 'Assists', 'Pts+Rebs+Asts', 'Fantasy Score', '3-PT Made', 'Pts+Rebs', 'Pts+Asts', 'Rebs+Asts', 'Free Throws Made', 'Blks+Stls', 'Blocked Shots', 'Steals', 'Turnovers']

    for item in data['data']:
        if item["attributes"]["stat_type"] in stat_types and item["relationships"]["league"]["data"]["id"] == '7':
            player_id = item['relationships']['new_player']['data']['id']
            player_name = players_df.loc[players_df['id'] == player_id, 'attributes.name'].values[0]
            player_pos = players_df.loc[players_df['id'] == player_id, 'attributes.position'].values[0]
            projections.append({
                "name": player_name,
                "position": player_pos,
                "stat_type": item["attributes"]["stat_type"],
                "line": item["attributes"]["line_score"],
                "opposing_team": item["attributes"]["description"]
            })
            
    df = pd.DataFrame(projections)
    return df

def get_team_abbreviation():
    url = 'https://www.balldontlie.io/api/v1/teams'
    response = urllib.request.urlopen(url)
    teams = json.loads(response.read().decode())

    team_abbreviation = {}
    for team in teams['data']:
        team_abbreviation[team['id']] = team['abbreviation']
        
    return team_abbreviation

def get_player_stats(player_name:str):

    url_name = player_name.replace(' ', '%20')
    url = f'https://www.balldontlie.io/api/v1/players?search={url_name}'

    response = urllib.request.urlopen(url)
    players = json.loads(response.read().decode())
    
    player_id = players['data'][0]['id']
    team_id = players['data'][0]['team']['id']
    
    url = f'https://www.balldontlie.io/api/v1/stats?seasons[]=2022&player_ids[]={player_id}'
    
    response = urllib.request.urlopen(url)
    stats = json.loads(response.read().decode())

    games = []

    for dat in stats['data']:
        date = dat['game']['date'][:10]
        if team_id == dat['game']['home_team_id']:
            opponent = ABB[dat['game']['visitor_team_id']]
        else:
            opponent = ABB[dat['game']['home_team_id']]
        points = dat['pts']
        rebounds = dat['reb']
        assists = dat['ast']
        steals = dat['stl']
        blocks = dat['blk']
        turnovers = dat['turnover']
        minutes = dat['min']
        fg3m = dat['fg3m']
        ftm = dat['ftm']
        fantasy = points + 1.2*rebounds + 1.5*assists + 3*steals + 3*blocks - turnovers

        if int(minutes) < 1:
            continue
        
        games.append([date, opponent, minutes, points, rebounds, assists, points+rebounds+assists, fantasy, fg3m, points+rebounds, points+assists, rebounds+assists, ftm, blocks+steals, blocks, steals, turnovers])
    
    df = pd.DataFrame(games, columns=['Date', 'Opposing_Team','Minutes','Points', 'Rebounds', 'Assists', 'Pts+Rebs+Asts', 'Fantasy Score', '3-PT Made', 'Pts+Rebs', 'Pts+Asts', 'Rebs+Asts', 'Free Throws Made', 'Blks+Stls', 'Blocked Shots', 'Steals', 'Turnovers'])
    df['Date'] = pd.to_datetime(df['Date'])
    df.sort_values(by=['Date'], inplace=True, ignore_index=True)
    return df

def pick(bet_info, sleep:bool=False, pr:bool=False):
    if bet_info["name"] in visited:
        df = visited[bet_info["name"]]
    else: 
        df = get_player_stats(bet_info["name"])
        visited[bet_info["name"]] = df
        
        if sleep:
            time.sleep(2)
        
    stat_type = bet_info["stat_type"]
    line = float(bet_info["line"])
    opp = bet_info["opposing_team"]
    pos = bet_info["position"]
    
    mean = df[stat_type].mean()
    std_dev = df[stat_type].std()
    variance = df[stat_type].var()
    z_score = (line - mean) / std_dev
   
    if z_score > 0:
        prediction = 'under'
    else:
        prediction = 'over'

    if pr:
        print(df[['Date', 'Opposing_Team', 'Minutes', stat_type]])
        print()
        print("Player: ", bet_info["name"])
        print("Stat Type: ", stat_type)
        print("Line: ", line)
        print("Opponent: ", opp)
        print("Position: ", pos)
        print()
        print("Mean: ", mean)
        print("Standard Deviation: ", std_dev)
        print("Variance: ", variance)
        print("Z-Score: ", z_score)
        print()
        print("Prediction: ", prediction)
        print()
    
    return ((abs(z_score), prediction, bet_info["name"], stat_type, line))

def getBet(df, player, stat_type):
    pick(df.loc[(df['name'] == player) & (df['stat_type'] == stat_type)].iloc[0], pr=True)

def getBetManual(player, stat_type, line, opp, pos):
    pick({"name": player, "stat_type": stat_type, "line": line, "opposing_team": opp, "position": pos}, pr=True)

def findBestPicks(n:int=10, one:bool=False, pr:bool=False):
    sleep = True
    if visited:
        sleep = False

    notFound = set()
    
    df = getPicks()

    picks = []
    print()
    print("Gathering Data...")
    for index, row in tqdm(df.iterrows(), total=df.shape[0]):
        if row["name"] in notFound:
            continue
        try:
            temp = pick(row, sleep, pr)
        except Exception as e:
            print(e, row["name"])
            notFound.add(row["name"])
            continue
        picks.append(temp)
            
    save(visited, "visited.pkl")
        
    picks = sorted(picks)[-n:][::-1]
    print()
    print("Safest Picks:")
    print()
    for p in picks:
        getBet(df, p[2], p[3])
        if one:
            input()
    print()
    
ABB = {
       1: 'ATL', 
       2: 'BOS', 
       3: 'BKN', 
       4: 'CHA', 
       5: 'CHI', 
       6: 'CLE', 
       7: 'DAL', 
       8: 'DEN', 
       9: 'DET', 
       10: 'GSW', 
       11: 'HOU', 
       12: 'IND', 
       13: 'LAC', 
       14: 'LAL', 
       15: 'MEM', 
       16: 'MIA', 
       17: 'MIL', 
       18: 'MIN', 
       19: 'NOP', 
       20: 'NYK', 
       21: 'OKC', 
       22: 'ORL', 
       23: 'PHI', 
       24: 'PHX', 
       25: 'POR', 
       26: 'SAC', 
       27: 'SAS', 
       28: 'TOR', 
       29: 'UTA', 
       30: 'WAS'
                }

visited = {}
# visited = load('visited.pkl')

findBestPicks()
