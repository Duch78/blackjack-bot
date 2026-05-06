import discord
from discord.ext import commands
import random
import json
import os
import asyncio

# =========================
# BOT CONFIG
# =========================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# =========================
# 🃏 DECK
# =========================
suits = ["♠️", "♥️", "♦️", "♣️"]
ranks = ["A","2","3","4","5","6","7","8","9","10","J","Q","K"]

def new_deck():
    deck = [(r, s) for s in suits for r in ranks]
    random.shuffle(deck)
    return deck

def card_value(card):
    r = card[0]
    if r in ["J","Q","K"]:
        return 10
    if r == "A":
        return 11
    return int(r)

def hand_value(hand):
    v = sum(card_value(c) for c in hand)
    aces = sum(1 for c in hand if c[0] == "A")
    while v > 21 and aces:
        v -= 10
        aces -= 1
    return v

def show(hand):
    return " ".join(f"{r}{s}" for r, s in hand)

# =========================
# 💰 ECONOMY
# =========================
if not os.path.exists("bank.json"):
    json.dump({}, open("bank.json","w"))

def bank():
    return json.load(open("bank.json"))

def save(b):
    json.dump(b, open("bank.json","w"), indent=4)

def get_bal(uid):
    b = bank()
    return b.get(str(uid), 1000)

def add_bal(uid, amt):
    b = bank()
    b[str(uid)] = b.get(str(uid), 1000) + amt
    save(b)

# =========================
# 🎰 CASINO ANIMATION
# =========================
async def casino_anim(interaction, text, delay=1.0):
    msg = await interaction.original_response()
    await msg.edit(content=text)
    await asyncio.sleep(delay)

# =========================
# 🎮 GAME CLASS
# =========================
class BJGod(discord.ui.View):
    def __init__(self, ctx, bet):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.bet = bet
        self.deck = new_deck()

        self.player = [self.deck.pop(), self.deck.pop()]
        self.dealer = [self.deck.pop(), self.deck.pop()]

        self.split_hands = []
        self.current = 0
        self.double_used = False
        self.uid = ctx.author.id

    async def interaction_check(self, i):
        return i.user.id == self.uid

    def current_hand(self):
        return self.player

    def dealer_play(self):
        while hand_value(self.dealer) < 17:
            self.dealer.append(self.deck.pop())

    def payout(self, result):
        if result == "bj":
            add_bal(self.uid, int(self.bet * 1.5))
        elif result == "win":
            add_bal(self.uid, self.bet)
        elif result == "lose":
            add_bal(self.uid, -self.bet)

    # =========================
    # 🎨 EMBED
    # =========================
    def render(self, reveal=False):
        dealer_hand = self.dealer if reveal else [self.dealer[0], ("❓","")]

        embed = discord.Embed(
            title="🎰 BLACKJACK • CASINO ROYAL",
            color=0xFFD700
        )

        embed.add_field(
            name="🃏 Joueur",
            value=f"{show(self.player)}\nScore: **{hand_value(self.player)}**",
            inline=False
        )

        embed.add_field(
            name="🎲 Dealer",
            value=f"{show(dealer_hand)}",
            inline=False
        )

        embed.add_field(
            name="💰 Mise",
            value=f"{self.bet}$",
            inline=True
        )

        embed.set_footer(text="🎲 Casino Royal - Good luck!")

        return embed

    # =========================
    # 🃏 HIT
    # =========================
    @discord.ui.button(label="🎯 HIT", style=discord.ButtonStyle.success)
    async def hit(self, i, b):

        hand = self.current_hand()

        await i.response.edit_message(
            content="🎴 Tirage en cours...",
            embed=self.render(),
            view=self
        )

        await asyncio.sleep(1.2)

        card = self.deck.pop()
        hand.append(card)

        await i.edit_original_response(
            content=f"🃏 Carte reçue : **{card[0]}{card[1]}**",
            embed=self.render(),
            view=self
        )

        await asyncio.sleep(1)

        if hand_value(hand) > 21:
            await self.end(i)

    # =========================
    # 🛑 STAND
    # =========================
    @discord.ui.button(label="🛑 STAND", style=discord.ButtonStyle.danger)
    async def stand(self, i, b):

        await i.response.edit_message(
            content="🎲 Le joueur reste... le dealer joue...",
            embed=self.render(),
            view=self
        )

        await asyncio.sleep(2)

        await self.end(i)

    # =========================
    # 💣 END GAME
    # =========================
    async def end(self, i):

        await i.response.edit_message(
            content="🎲 Révélation du dealer...",
            embed=self.render(reveal=True),
            view=self
        )

        await asyncio.sleep(2)

        self.dealer_play()

        p = hand_value(self.player)
        d = hand_value(self.dealer)

        await asyncio.sleep(1)

        if p == 21 and len(self.player) == 2:
            result = "bj"
            txt = "🎉 BLACKJACK ROYAL"
            color = 0x00ff00

        elif p > 21:
            result = "lose"
            txt = "💥 BUST"
            color = 0xff0000

        elif d > 21 or p > d:
            result = "win"
            txt = "🏆 VICTOIRE"
            color = 0x00ff00

        elif p < d:
            result = "lose"
            txt = "😢 DÉFAITE"
            color = 0xff0000

        else:
            result = "push"
            txt = "🤝 ÉGALITÉ"
            color = 0xffff00

        self.payout(result)

        for b in self.children:
            b.disabled = True

        embed = discord.Embed(
            title="🏁 FIN DE PARTIE",
            description=txt,
            color=color
        )

        embed.add_field(name="🃏 Joueur", value=f"{show(self.player)} ({p})", inline=False)
        embed.add_field(name="🎲 Dealer", value=f"{show(self.dealer)} ({d})", inline=False)

        await i.edit_original_response(embed=embed, view=self)

# =========================
# 🎮 COMMANDES
# =========================
@bot.command()
async def blackjack(ctx, bet: int):

    if bet <= 0:
        return await ctx.send("❌ Mise invalide")

    if get_bal(ctx.author.id) < bet:
        return await ctx.send("❌ Pas assez d'argent")

    view = BJGod(ctx, bet)

    await ctx.send(embed=view.render(), view=view)

@bot.command()
async def balance(ctx):
    await ctx.send(f"💰 Solde : {get_bal(ctx.author.id)}$")

# =========================
# 🚀 RUN BOT
# =========================
bot.run(os.getenv("DISCORD_TOKEN"))
