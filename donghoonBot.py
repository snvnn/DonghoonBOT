# This example requires the 'message_content' privileged intent to function.
 
import asyncio
 
import discord
import yt_dlp as youtube_dl
 
from discord.ext import commands
from dico_token import Token
import os

from collections import deque

# FFmpeg 상대 경로 설정 (현재 소스 코드와 같은 디렉토리에 있는 ffmpeg.exe)
FFMPEG_PATH = os.path.join(os.getcwd(), "ffmpeg.exe")

# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''
 
 
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',  # bind to ipv4 since ipv6 addresses cause issues sometimes
}
 
ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}
 
ytdl = youtube_dl.YoutubeDL(ytdl_format_options)
queue = deque()
nowPlaying = False

# youtube 음악과 로컬 음악의 재생을 구별하기 위한 클래스 작성.
class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
 
        self.data = data
 
        self.title = data.get('title')
        self.url = data.get('url')
 
    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
 
        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]
 
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)
 
 

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.is_playing = False
        self.queue = deque()  # 인스턴스 변수로 큐 관리

    async def play_next(self, ctx):
        if len(self.queue) > 0:  # self.queue로 변경
            self.is_playing = True
            next_url = self.queue.popleft()  # self.queue로 변경
            try:
                async with ctx.typing():
                    player = await YTDLSource.from_url(next_url, loop=self.bot.loop, stream=True)
                    ctx.voice_client.play(player, after=lambda e: self.after_play(ctx) if e is None else print(f'Player error: {e}'))
                await ctx.send(f'Now playing: {player.title}')
            except Exception as e:
                await ctx.send(f"Error playing the song: {e}")
                self.is_playing = False
                await self.play_next(ctx)  # 다음 곡 재생 시도
        else:
            self.is_playing = False

 
    def after_play(self, ctx):
        coro = self.play_next(ctx)
        fut = asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
        try:
            fut.result()
        except Exception as e:
            print(f"Error playing next song: {e}")


    @commands.command()
    async def play(self, ctx, *, url):
        """유튜브 URL을 큐에 추가하고, 음악이 재생 중이 아니면 재생을 시작"""
        self.queue.append(url)  # self.queue로 변경
        await ctx.send(f"Added to the queue. Position in queue: {len(self.queue)}")  # self.queue로 변경

        if not self.is_playing:  # 현재 재생 중인 음악이 없으면
            await self.play_next(ctx)  # 즉시 재생 시작

    @commands.command()
    async def stop(self, ctx):
        """음성 채널에서 봇을 나가게 하고 대기열을 초기화"""
        queue.clear()  # 대기열 비우기
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
        self.is_playing = False  # 음악 재생 상태 초기화

    @commands.command()
    async def skip(self, ctx):
        """현재 재생 중인 음악을 스킵하고 대기열의 다음 곡을 재생"""
        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()  # 현재 음악을 멈추면 after 콜백이 호출되어 다음 곡을 재생

 
    @commands.command()
    async def join(self, ctx):
        """Joins a voice channel"""
        
        channel = ctx.author.voice.channel
 
        if ctx.voice_client is not None:
            return await ctx.voice_client.move_to(channel)
 
        await channel.connect()
 
    @commands.command()
    async def volume(self, ctx, volume: int):
        """Changes the player's volume"""
 
        if ctx.voice_client is None:
            return await ctx.send("Not connected to a voice channel.")
 
        ctx.voice_client.source.volume = volume / 100
        await ctx.send(f"Changed volume to {volume}%")
            
    @commands.command()
    async def pause(self, ctx):
        ''' 음악을 일시정지 할 수 있습니다. '''
 
        if ctx.voice_client.is_paused() or not ctx.voice_client.is_playing():
            await ctx.send("음악이 이미 일시 정지 중이거나 재생 중이지 않습니다.")
            
        ctx.voice_client.pause()
            
    @commands.command()
    async def resume(self, ctx):
        ''' 일시정지된 음악을 다시 재생할 수 있습니다. '''
 
        if ctx.voice_client.is_playing() or not ctx.voice_client.is_paused():
            await ctx.send("음악이 이미 재생 중이거나 재생할 음악이 존재하지 않습니다.")
            
        ctx.voice_client.resume()
 
    @play.before_invoke
    async def ensure_voice(self, ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                await ctx.author.voice.channel.connect()
            else:
                await ctx.send("You are not connected to a voice channel.")
                raise commands.CommandError("Author not connected to a voice channel.")
        elif ctx.voice_client.is_playing():
            ctx.voice_client.stop()
 
 
intents = discord.Intents.default()
intents.message_content = True
 
bot = commands.Bot(
    command_prefix=commands.when_mentioned_or("++"),
    description='Relatively simple music bot example',
    intents=intents,
)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    await bot.change_presence(status=discord.Status.online) #온라인    
    await bot.change_presence(activity=discord.Game(name="총선 말아먹기"))    
    print('------')
 
 
async def main():
    async with bot:
        await bot.add_cog(Music(bot))
        await bot.start(Token)
 
 
asyncio.run(main())