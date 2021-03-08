from .github import Github
from .ping import Ping
from .uptime import Uptime
from .dog import Dog
from .coin import Coin
from .role import Role
from .gamestats import Gamestats
from .playerstats import Playerstats
from .top import Top

def setup(client):
    client.add_cog(Github(client))
    client.add_cog(Ping(client))
    client.add_cog(Uptime(client))
    client.add_cog(Dog(client))
    client.add_cog(Coin(client))
    client.add_cog(Role(client))
    client.add_cog(Gamestats(client))
    client.add_cog(Playerstats(client))
    client.add_cog(Top(client))
