"""
IdleWorlds -- Modular Server Event system: reference implementation.

Deterministic. Given the same server-day seed string and the same history,
every client and every server shard produces the identical event. The PRNG is
mulberry32 so the JS side can be a line-for-line port.

Data model per module:
    (id, name, (primary_tag, *secondary_tags), surfaces, blurb,
     (mag_I, mag_II, mag_III), param_key_or_None)
"""

MASK = 0xFFFFFFFF


def fnv1a(text):
    h = 0x811C9DC5
    for ch in text.encode('utf-8'):
        h ^= ch
        h = (h * 0x01000193) & MASK
    return h


def mulberry32(seed):
    """Port of the canonical mulberry32. Returns a float in [0, 1)."""
    state = [seed & MASK]

    def rnd():
        state[0] = (state[0] + 0x6D2B79F5) & MASK
        t = state[0]
        t = ((t ^ (t >> 15)) * (1 | t)) & MASK
        t = ((t + (((t ^ (t >> 7)) * (61 | t)) & MASK)) & MASK) ^ t
        return ((t ^ (t >> 14)) & MASK) / 4294967296.0

    return rnd


class Rng:
    def __init__(self, seed_string):
        self.seed_string = seed_string
        self._r = mulberry32(fnv1a(seed_string))

    def next(self):
        return self._r()

    def pick(self, seq):
        return seq[int(self.next() * len(seq))]

    def pick_n(self, seq, n):
        pool = list(seq)
        out = []
        for _ in range(n):
            out.append(pool.pop(int(self.next() * len(pool))))
        return out

    def weighted(self, pairs):
        """pairs: list of (item, weight)."""
        total = sum(w for _, w in pairs)
        roll = self.next() * total
        acc = 0.0
        for item, w in pairs:
            acc += w
            if roll < acc:
                return item
        return pairs[-1][0]


# ---------------------------------------------------------------- parameters

ZONES = ['Zone %02d' % n for n in range(1, 35)]
SKILLS = ['Mining', 'Woodcutting', 'Fishing', 'Foraging', 'Smithing',
          'Tailoring', 'Cooking', 'Alchemy', 'Jewelcrafting', 'Construction']
GEAR_SLOTS = ['Head', 'Chest', 'Legs', 'Hands', 'Feet', 'Main Hand',
              'Off Hand', 'Cloak', 'Amulet', 'Ring I', 'Ring II', 'Belt']
FAMILIES = ['Beastkin', 'Undead', 'Humanoid', 'Elemental', 'Aberrant',
            'Construct', 'Dragonkin', 'Insectoid']
RESOURCES = ['Timber', 'Ore', 'Fish', 'Herbs', 'Cloth', 'Leather',
             'Gemstone', 'Stone']
DAMAGE_TYPES = ['Slash', 'Pierce', 'Blunt', 'Fire', 'Frost', 'Shock',
                'Venom', 'Arcane']
WINDOWS = ['%02d:00-%02d:00 server time' % (h, (h + 4) % 24) for h in range(0, 20)]
TIER_BANDS = ['Tiers %d-%d' % (n, n + 4) for n in range(1, 31)]

PARAM_POOLS = {
    'ZONE': ZONES,
    'SKILL': SKILLS,
    'GEAR_SLOT': GEAR_SLOTS,
    'FAMILY': FAMILIES,
    'RESOURCE': RESOURCES,
    'DAMAGE_TYPE': DAMAGE_TYPES,
    'WINDOW': WINDOWS,
    'TIER_BAND': TIER_BANDS,
}


def roll_param(rng, key):
    if key is None:
        return None
    if key == 'SKILL3':
        return ', '.join(rng.pick_n(SKILLS, 3))
    if key == 'ROTATION':
        return ' -> '.join(rng.pick_n(SKILLS, 4))
    if key == 'LEGACY':
        return None  # resolved against the event archive at publish time
    return rng.pick(PARAM_POOLS[key])


PARAM_COUNT = {
    None: 1, 'SKILL3': 120, 'ROTATION': 5040, 'LEGACY': 80,
    'ZONE': 34, 'SKILL': 10, 'GEAR_SLOT': 12, 'FAMILY': 8,
    'RESOURCE': 8, 'DAMAGE_TYPE': 8, 'WINDOW': 20, 'TIER_BAND': 30,
}


# ------------------------------------------------------------------- modules

SLOT_A = [
    ('A1', 'Coin Flood', ('ECONOMY', 'LOOT'), {'GLOBAL'},
     'Every gold source on the server pays more.',
     ('+25% gold', '+60% gold', '+120% gold'), None),
    ('A2', 'Rich Veins', ('GATHERING', 'ECONOMY'), {'GATHER'},
     'Gathering nodes give up a second helping.',
     ('10% double-yield', '20% double-yield', '35% double-yield'), None),
    ('A3', "Master's Hand", ('CRAFTING', 'ECONOMY'), {'CRAFT'},
     'Crafts occasionally come off the bench twice.',
     ('8% free extra craft', '15% free extra craft', '25% free extra craft'), None),
    ('A4', 'Battle Fervour', ('COMBAT', 'XP'), {'COMBAT'},
     'Combat experience surges.',
     ('+30% combat XP', '+70% combat XP', '+150% combat XP'), None),
    ('A5', 'Deep Pockets', ('LOOT', 'COMBAT'), {'COMBAT', 'GATHER'},
     'Item Find rises for everyone, equipped or not.',
     ('+15 Item Find', '+35 Item Find', '+75 Item Find'), None),
    ('A6', "Fortune's Eye", ('LOOT', 'ECONOMY'), {'COMBAT', 'GATHER'},
     'Gold Find rises for everyone, equipped or not.',
     ('+20 Gold Find', '+45 Gold Find', '+90 Gold Find'), None),
    ('A7', "Quartermaster's Ledger", ('WORKORDER', 'ECONOMY'), {'WORKORDER'},
     'Work Order payouts are inflated.',
     ('+30% WO reward', '+65% WO reward', '+130% WO reward'), None),
    ('A8', 'Tireless', ('GATHERING', 'CRAFTING'), {'GATHER', 'CRAFT'},
     'Every non-combat action ticks faster.',
     ('+10% action speed', '+20% action speed', '+35% action speed'), None),
    ('A9', 'Warband', ('COMBAT',), {'COMBAT'},
     'Warfare climbs across the roster.',
     ('+10% Warfare', '+22% Warfare', '+45% Warfare'), None),
    ('A10', 'Second Wind', ('COMBAT', 'RISK'), {'COMBAT'},
     'Recovery is fast and dying costs less.',
     ('x2 recovery, -50% death penalty', 'x3 recovery, -75% death penalty',
      'x5 recovery, no death penalty'), None),
    ('A11', "Salvager's Luck", ('LOOT', 'CRAFTING'), {'COMBAT', 'GATHER'},
     'Enhancement materials fall out of ordinary actions.',
     ('5% bonus material', '10% bonus material', '18% bonus material'), None),
    ('A12', "Foreman's Whistle", ('VILLAGE', 'CRAFTING'), {'VILLAGE'},
     'Building Parts come quicker and cheaper.',
     ('+25% Parts XP, -10% bill', '+55% Parts XP, -20% bill',
      '+110% Parts XP, -35% bill'), None),
    ('A13', 'Silver Tongue', ('ECONOMY',), {'TRADE', 'GLOBAL'},
     'Vendors buy high and sell low.',
     ('-10% buy / +15% sell', '-20% buy / +30% sell', '-33% buy / +60% sell'), None),
    ('A14', "Apprentice's Boon", ('XP', 'SOCIAL'), {'GLOBAL'},
     'Your three lowest skills catch up fast.',
     ('+50% XP on lowest 3', '+110% XP on lowest 3', '+220% XP on lowest 3'), None),
    ('A15', 'Restless Traveller', ('EXPLORATION', 'COMBAT'), {'COMBAT', 'GLOBAL'},
     'Zone gates relax and travel is free.',
     ('-3 zone level req', '-6 zone level req', '-10 zone level req'), None),
    ('A16', 'Overflow', ('ECONOMY', 'XP'), {'GLOBAL'},
     'The idle bucket holds far more before it spills.',
     ('+4h idle cap', '+8h idle cap', '+16h idle cap'), None),
    ('A17', 'Gem-Sight', ('LOOT', 'CRAFTING'), {'COMBAT', 'GATHER'},
     'Gems and sockets surface everywhere.',
     ('x2 gem drops', 'x3 gem drops', 'x5 gem drops'), None),
    ('A18', "Alchemist's Surplus", ('CRAFTING', 'COMBAT'), {'CRAFT', 'COMBAT'},
     'Potions last longer and are often not spent.',
     ('+50% duration, 15% not consumed', '+100% duration, 30% not consumed',
      '+200% duration, 50% not consumed'), None),
    ('A19', 'Village Rally', ('VILLAGE', 'SOCIAL'), {'VILLAGE', 'GLOBAL'},
     'Every add-on and building buff is amplified.',
     ('+25% add-on buffs', '+50% add-on buffs', '+100% add-on buffs'), None),
    ('A20', 'Task Bounty', ('WORKORDER', 'XP'), {'WORKORDER'},
     'Task-tier completions pay a bounty.',
     ('x1.5 task rewards', 'x2 task rewards', 'x3 task rewards'), None),
]

SLOT_B = [
    ('B1', 'Swarm', ('COMBAT', 'RISK'), {'COMBAT'},
     'Encounters bring friends. Per-kill rewards are unchanged, so the day is '
     'strictly denser, not strictly richer.',
     ('+1 enemy per fight', '+2 enemies per fight', '+4 enemies per fight'),
     None, ('Teeming', 'Endless', 'Ravening', 'Boundless')),
    ('B2', 'Elite Vanguard', ('COMBAT', 'LOOT'), {'COMBAT'},
     'A share of spawns are Elites: double health, two-and-a-half times the take.',
     ('10% Elites', '20% Elites', '35% Elites'),
     None, ('Crowned', "Vanguard's", 'Imperial', "Warlord's")),
    ('B3', 'Brittle Steel', ('CRAFTING', 'RISK'), {'CRAFT'},
     'Enhancement is far riskier, but every success lands one level deeper.',
     ('+15pp failure, +1 level on success', '+25pp failure, +1 level on success',
      '+40pp failure, +1 level on success'),
     None, ('Brittle', 'Tempered', 'Reckless', 'Hammered')),
    ('B4', 'Blind Draw', ('LOOT', 'RISK'), {'GLOBAL'},
     'Every drop rolls twice and keeps the better roll. Nothing is previewed '
     'anywhere in the UI until it is claimed.',
     ('best of 2 on rares', 'best of 2 on all drops', 'best of 3 on all drops'),
     None, ('Veiled', 'Hidden', 'Shrouded', 'Unseen')),
    ('B5', 'Iron Rations', ('COMBAT', 'RISK'), {'COMBAT'},
     'Healing is halved; the survivors learn faster for it.',
     ('-50% healing, +40% combat XP', '-50% healing, +80% combat XP',
      '-50% healing, +150% combat XP'),
     None, ('Starving', 'Lean', 'Gaunt', 'Hollow')),
    ('B6', 'Rush Orders', ('WORKORDER', 'RISK'), {'WORKORDER'},
     'Shorter fuses, bigger quotas.',
     ('-25% timer, +50% quantity', '-40% timer, +90% quantity',
      '-60% timer, +150% quantity'),
     None, ('Hurried', 'Frantic', 'Breakneck', 'Clamouring')),
    ('B7', 'Heavy Haul', ('GATHERING', 'RISK'), {'GATHER'},
     'Carry less, gather more. Bank trips become the real cost.',
     ('-30% carry, +40% yield', '-45% carry, +80% yield', '-60% carry, +150% yield'),
     None, ('Laden', 'Burdened', 'Groaning', 'Overladen')),
    ('B8', 'Contested Ground', ('SOCIAL', 'COMBAT'), {'COMBAT'},
     'A server-wide kill counter runs in the focused area; everyone shares the '
     'escalating bonus it pays out.',
     ('+5% per 10k kills, cap +25%', '+5% per 10k kills, cap +50%',
      '+5% per 5k kills, cap +75%'),
     None, ('Contested', 'Warring', 'Thronged', 'Embattled')),
    ('B9', 'Tempered Tools', ('GATHERING', 'RISK'), {'GATHER'},
     'Gathering is slower per action and much larger per action, which rewards '
     'long uninterrupted sessions over check-ins.',
     ('-25% speed, x2 yield', '-35% speed, x2.5 yield', '-50% speed, x3.5 yield'),
     None, ('Patient', 'Slow-Burning', 'Deliberate', 'Enduring')),
    ('B10', 'Night Shift', ('RISK', 'SOCIAL'), {'GLOBAL'},
     'Nothing happens for the first half of the server day. Then everything '
     'happens harder.',
     ('dormant 12h, then x1.5', 'dormant 12h, then x2', 'dormant 12h, then x2.5'),
     None, ('Nocturnal', 'Midnight', 'Twilit', 'Waking')),
    ('B11', 'Glass Cannon', ('COMBAT', 'RISK'), {'COMBAT'},
     'Damage dealt and damage taken both climb, dealt slightly faster.',
     ('+50% dealt / +40% taken', '+100% dealt / +80% taken',
      '+200% dealt / +150% taken'),
     None, ('Brittle-Boned', 'Reckless', 'Sundering', 'Frenzied')),
    ('B12', 'Tithe', ('ECONOMY', 'SOCIAL'), {'GLOBAL'},
     'A slice of every coin earned goes into a server pot, paid back at reset '
     'to contributors at one and a half times what they put in.',
     ('10% tithe', '15% tithe', '25% tithe'),
     None, ('Tithed', 'Sworn', 'Covenant', 'Pledged')),
    ('B13', 'Rivalry', ('SOCIAL', 'XP'), {'GLOBAL'},
     'A public leaderboard opens for the themed activity and pays the top of it '
     'at reset.',
     ('top 25 rewarded', 'top 100 rewarded', 'top 500 rewarded'),
     None, ('Rival', 'Proving', 'Contested', 'Crowning')),
    ('B14', 'Unstable Enchantment', ('CRAFTING', 'RISK'), {'GLOBAL'},
     'Enchantments on equipped gear reroll to a random enchantment of the same '
     'tier on a timer. Nothing is destroyed; the loadout simply will not sit still.',
     ('reroll every 4h', 'reroll every 2h', 'reroll every 1h'),
     None, ('Unstable', 'Shifting', 'Wild', 'Unbound')),
    ('B15', 'Wandering Merchant', ('ECONOMY', 'EXPLORATION'), {'TRADE', 'GLOBAL'},
     'A merchant with a randomly drawn stock sets up in one zone and moves every '
     'few hours.',
     ('6 lines at 60% price', '10 lines at 50% price', '15 lines at 40% price'),
     'ZONE', ('Wandering', 'Vagrant', 'Gilded', 'Far-Roaming')),
    ('B16', 'Scarcity', ('ECONOMY', 'GATHERING'), {'GATHER', 'CRAFT', 'TRADE'},
     'One resource family stops dropping entirely. Anything already made from it '
     'is worth a fortune.',
     ('x2 value on affected goods', 'x3 value on affected goods',
      'x5 value on affected goods'),
     'RESOURCE', ('Barren', 'Withered', 'Hungering', 'Fallow')),
    ('B17', 'Conscription', ('WORKORDER', 'RISK'), {'WORKORDER'},
     'Finishing a Work Order reassigns you to a different skill. Each link in the '
     'chain pays better than the last.',
     ('+20% per chain link', '+35% per chain link', '+50% per chain link'),
     None, ('Conscript', 'Levied', 'Marching', 'Summoned')),
    ('B18', 'Momentum', ('GATHERING', 'CRAFTING'), {'GATHER', 'CRAFT'},
     'Repeating the same action stacks a bonus. Switching resets it to zero.',
     ('+1% per action, cap +25%', '+1% per action, cap +50%',
      '+1% per action, cap +100%'),
     None, ('Relentless', 'Unbroken', 'Ceaseless', 'Driving')),
    ('B19', "Hunter's Mark", ('COMBAT', 'LOOT'), {'COMBAT'},
     'One enemy family is marked. It is worth several times normal; everything '
     'else is worth rather less.',
     ('x3 marked / x0.6 rest', 'x4 marked / x0.6 rest', 'x6 marked / x0.6 rest'),
     'FAMILY', ('Hunted', 'Marked', 'Stalking', "Quarry's")),
    ('B20', 'Doubling Down', ('RISK', 'LOOT'), {'GLOBAL'},
     'Any reward can be pushed: better than even odds to double it, otherwise it '
     'is gone. Opt-in, per reward.',
     ('55% to double, 3 pushes/h', '60% to double, 5 pushes/h',
      '65% to double, unlimited'),
     None, ("Gambler's", 'Fated', "Chancer's", "Devil's")),
]

SLOT_C = [
    ('C1', 'Zone Lock', ('EXPLORATION',), {'COMBAT', 'GATHER'},
     'One zone becomes the epicentre; the rest of the world is damped.',
     ('x1.5 inside / x0.75 outside', 'x2 inside / x0.75 outside',
      'x3 inside / x0.75 outside'), 'ZONE'),
    ('C2', 'Tier Band', ('EXPLORATION', 'COMBAT'), {'COMBAT', 'GATHER'},
     'Only a five-tier band of content is affected.',
     ('x1.5 in band', 'x2 in band', 'x2.5 in band'), 'TIER_BAND'),
    ('C3', 'Skill Trio', ('XP', 'GATHERING'), {'GATHER', 'CRAFT', 'VILLAGE'},
     'Three skills carry the event; the other seven have a normal day.',
     ('x1.5 on the trio', 'x2 on the trio', 'x2.5 on the trio'), 'SKILL3'),
    ('C4', 'Spotlight', ('XP',), {'GATHER', 'CRAFT', 'VILLAGE'},
     'One skill only, and it is turned up hard.',
     ('x2 on that skill', 'x2.5 on that skill', 'x3 on that skill'), 'SKILL'),
    ('C5', 'Element Ascendant', ('COMBAT',), {'COMBAT'},
     'One damage type is ascendant; event combat effects scale with using it.',
     ('x1.5 with that type', 'x2 with that type', 'x2.5 with that type'),
     'DAMAGE_TYPE'),
    ('C6', 'Slotwork', ('COMBAT', 'CRAFTING'), {'COMBAT'},
     'One equipment slot has its stats multiplied for the day.',
     ('x1.5 slot stats', 'x2 slot stats', 'x2.5 slot stats'), 'GEAR_SLOT'),
    ('C7', 'Set Surge', ('COMBAT', 'CRAFTING'), {'COMBAT'},
     'Set bonuses count extra pieces you are not wearing.',
     ('+1 phantom piece', '+2 phantom pieces', 'all sets active at 4 pieces'), None),
    ('C8', 'Hearthbound', ('VILLAGE', 'SOCIAL'), {'VILLAGE'},
     'Effects run through the village and scale with what has been built.',
     ('+4% per add-on, cap +40%', '+6% per add-on, cap +60%',
      '+8% per add-on, cap +80%'), None),
    ('C9', 'Estate', ('VILLAGE', 'ECONOMY'), {'VILLAGE', 'GLOBAL'},
     'Magnitude scales off housing tier, so the event rewards long-term investment.',
     ('+10% per housing tier', '+15% per housing tier', '+20% per housing tier'),
     None),
    ('C10', 'Sanctuary', ('XP', 'SOCIAL'), {'GLOBAL'},
     'Only content at or below your level minus ten is affected. A deliberate '
     'catch-up lens.',
     ('x2 on backfill content', 'x3 on backfill content', 'x4 on backfill content'),
     None),
    ('C11', 'Deep End', ('COMBAT', 'EXPLORATION'), {'COMBAT'},
     'The top five zones only.',
     ('x2 at the top', 'x2.5 at the top', 'x3 at the top'), None),
    ('C12', 'Open World', (), {'GLOBAL'},
     'No restriction at all -- but every other module drops one magnitude band '
     '(never below I). The safety valve and the wide, gentle day.',
     ('unrestricted, -1 band', 'unrestricted, -1 band', 'unrestricted, -1 band'),
     None),
    ('C13', 'Hour of Power', ('RISK', 'SOCIAL'), {'GLOBAL'},
     'A four-hour window is announced at reset. Inside it the event triples; '
     'outside it the event is halved.',
     ('x3 in window / x0.5 out', 'x4 in window / x0.5 out',
      'x5 in window / x0.5 out'), 'WINDOW'),
    ('C14', 'Rotation', ('EXPLORATION', 'XP'), {'GLOBAL'},
     'The focus walks through four drawn targets, six hours each.',
     ('x1.5 on the active target', 'x2 on the active target',
      'x2.5 on the active target'), 'ROTATION'),
    ('C15', 'Warfront', ('COMBAT',), {'COMBAT'},
     'Combat only.', ('x1.5 in combat', 'x2 in combat', 'x2.5 in combat'), None),
    ('C16', 'Harvest', ('GATHERING',), {'GATHER'},
     'Gathering only.',
     ('x1.5 gathering', 'x2 gathering', 'x2.5 gathering'), None),
    ('C17', 'Forge', ('CRAFTING',), {'CRAFT'},
     'Crafting and refining only.',
     ('x1.5 crafting', 'x2 crafting', 'x2.5 crafting'), None),
    ('C18', 'Ledger', ('WORKORDER', 'ECONOMY'), {'WORKORDER'},
     'Work Orders and task tiers only.',
     ('x1.5 on orders', 'x2 on orders', 'x2.5 on orders'), None),
    ('C19', 'Muster', ('SOCIAL', 'COMBAT'), {'COMBAT'},
     'Effects scale with how many players are in your zone right now.',
     ('+2% each, cap +40%', '+3% each, cap +50%', '+5% each, cap +60%'), None),
    ('C20', 'Watermark', ('SOCIAL', 'XP'), {'GLOBAL'},
     'Effects scale with how far past your own previous-day total you get. '
     'Competes with nobody but yesterday.',
     ('+1% per 5% over, cap +50%', '+1% per 4% over, cap +75%',
      '+1% per 3% over, cap +100%'), None),
]

SLOT_D = [
    ('D1', 'Great Learning', ('XP',), {'GLOBAL'},
     'All experience, every skill, all day.',
     ('x1.5 all XP', 'x2 all XP', 'x2.5 all XP'), None),
    ('D2', 'Spoils', ('LOOT',), {'GLOBAL'},
     'Drop quantities across the board.',
     ('x1.5 drop quantity', 'x2 drop quantity', 'x3 drop quantity'), None),
    ('D3', 'Wider Boon', ('XP',), {'GLOBAL'},
     "Today's Daily XP Boost covers more than its usual three skills.",
     ('5 skills boosted', '6 skills boosted', 'all 10 skills boosted'), None),
    ('D4', 'Free Rerolls', ('WORKORDER',), {'GLOBAL'},
     'Reroll tasks and Work Orders at no cost.',
     ('3 rerolls', '5 rerolls', 'unlimited rerolls'), None),
    ('D5', 'Event Currency', ('ECONOMY', 'SOCIAL'), {'GLOBAL'},
     'A token drops server-wide and an event shop stays open for 48 hours past '
     'reset, so nobody is punished for sleeping through the day.',
     ('6 shop lines', '10 shop lines', '15 shop lines'), None),
    ('D6', 'Regalia', ('SOCIAL',), {'GLOBAL'},
     'A title and banner named for this exact event, awarded on participation and '
     'never reissued. The permanent record that this day happened.',
     ('title', 'title + banner', 'title + banner + frame'), None),
    ('D7', 'Server Goal', ('SOCIAL',), {'GLOBAL'},
     'One global bar the whole server fills together.',
     ('1 reward tier', '2 reward tiers', '3 reward tiers'), None),
    ('D8', 'Milestone Chain', ('XP', 'LOOT'), {'GLOBAL'},
     'Personal milestones through the day, each paying more than the last.',
     ('3 milestones', '5 milestones', '7 milestones'), None),
    ('D9', 'Grace', ('CRAFTING',), {'GLOBAL'},
     'Guaranteed enhancement successes, banked per account.',
     ('1 guaranteed success', '2 guaranteed successes', '3 guaranteed successes'),
     None),
    ('D10', 'Gem Rain', ('LOOT', 'CRAFTING'), {'GLOBAL'},
     'Gems fall from everything.',
     ('x2 gems', 'x3 gems', 'x5 gems'), None),
    ('D11', 'Amnesty', ('ECONOMY',), {'GLOBAL'},
     'Every gold sink is switched off: travel, repair, respec, listing fees.',
     ('travel + repair free', 'travel + repair + respec free', 'all sinks free'),
     None),
    ('D12', 'Second Ledger', ('WORKORDER',), {'GLOBAL'},
     'Extra concurrent Work Order slots.',
     ('+1 slot', '+2 slots', '+3 slots'), None),
    ('D13', 'Construction Blitz', ('VILLAGE',), {'GLOBAL'},
     'The village goes up fast and cheap.',
     ('x2 speed, -10% Parts', 'x3 speed, -20% Parts', 'x5 speed, -30% Parts'), None),
    ('D14', 'The Rift', ('EXPLORATION', 'COMBAT'), {'GLOBAL'},
     'A temporary zone opens, level-scaled to each player, with its own loot table '
     'that closes at reset.',
     ('rift, 1 floor', 'rift, 3 floors', 'rift, 5 floors'), None),
    ('D15', 'Loot Echo', ('LOOT',), {'GLOBAL'},
     'Drops can duplicate, and the duplicate can duplicate.',
     ('8% echo', '12% echo', '20% echo'), None),
    ('D16', 'First Blood', ('LOOT', 'COMBAT'), {'GLOBAL'},
     'The first kills of each hour are guaranteed rares -- a shape that rewards '
     'checking in rather than parking.',
     ('first 5 per hour', 'first 10 per hour', 'first 20 per hour'), None),
    ('D17', 'Overreach', ('XP',), {'GLOBAL'},
     'Your highest skill counts as several levels higher for requirements and yields.',
     ('+3 effective levels', '+5 effective levels', '+8 effective levels'), None),
    ('D18', 'Overtime', ('ECONOMY',), {'GLOBAL'},
     'Idle and offline accrual pays at the full active rate for the event day.',
     ('100% offline rate, 8h', '100% offline rate, 16h', '100% offline rate, 24h'),
     None),
    ('D19', "Trader's Holiday", ('ECONOMY',), {'GLOBAL'},
     'Market tax is waived and vendors pay a premium.',
     ('no tax, +20% sell', 'no tax, +40% sell', 'no tax, +75% sell'), None),
    ('D20', 'Echo of Days', ('RISK', 'SOCIAL'), {'GLOBAL'},
     'One module from a randomly chosen past event returns as a fifth effect at '
     'magnitude I. The archive feeds itself.',
     ('1 revived module at I', '1 revived module at I', '2 revived modules at I'),
     'LEGACY'),
]

SLOTS = {'A': SLOT_A, 'B': SLOT_B, 'C': SLOT_C, 'D': SLOT_D}


def module_fields(entry):
    """Slot B carries a fifth adjective tuple; everything else does not."""
    mid, name, tags, surf, blurb, mags, param = entry[:7]
    adjectives = entry[7] if len(entry) > 7 else None
    return dict(id=mid, name=name, tags=tags, surfaces=surf, blurb=blurb,
                mags=mags, param=param, adjectives=adjectives)


# --------------------------------------------------------------------- names

THEME_NOUNS = {
    'COMBAT': ['Blood Moon', 'Warcry', 'Red Tide', 'Iron Harvest', 'Siegefall',
               'Bonefield', 'Long Battle', 'Hollow Crown', 'Ashen Vigil',
               "Reaver's Hour"],
    'GATHERING': ['Green Tide', 'First Harvest', 'Deep Seam', 'Rootfall',
                  'Amber Season', 'Long Gather', 'Wildgrowth', 'Stonebloom',
                  'Sapmoon', 'Full Cart'],
    'CRAFTING': ['Forgefire', 'Anvil Chorus', 'Emberwork', 'Quenching',
                 "Maker's Hour", 'Ashfall Forge', 'Loomsong', 'Bellowsnight',
                 'Fine Seam', 'Hammerfall'],
    'ECONOMY': ['Gilded Hour', 'Grand Exchange', 'Coinfall', "Merchant's Moon",
                'Ledger', 'Golden Wake', 'Copper Rain', 'Long Market',
                'Vault Season', 'Purse-Cut'],
    'WORKORDER': ['Muster Roll', 'Quota', 'Standing Order', 'Requisition',
                  'Warrant Day', "Foreman's Call", 'Backlog', 'Docket',
                  'Signed and Sealed', 'Order of the Day'],
    'LOOT': ['Spoils', 'Glittering Hour', 'Hoardfall', 'Treasurewake',
             'Bright Take', 'Cache Season', 'Windfall', 'Full Pack', 'Trove',
             'Scattered Riches'],
    'XP': ['Enlightenment', 'Long Lesson', 'Ascension', 'Mindfire', 'Steep Climb',
           'Revelation', 'Whetstone', 'Quickening', 'Insight', 'Breakthrough'],
    'EXPLORATION': ['Wayfare', 'Open Road', 'Farwander', 'Uncharted',
                    'Horizonfall', 'Long Path', 'Trailblaze', 'Strange Country',
                    'Far Marches', 'Driftlands'],
    'VILLAGE': ['Raising', 'Hearthlight', 'Common Good', 'Foundation Day',
                'Rooftree', 'Village Wake', 'Cornerstone', 'Bonfire Night',
                'Long Table', 'Homecoming'],
    'SOCIAL': ['Convergence', 'Gathering', 'Assembly', 'Chorus', 'Great Meet',
               'Commonwake', 'Many Hands', 'Shared Hour', 'Congress',
               'Fellowship'],
    'RISK': ['Gamble', "Fool's Wager", 'Knife-Edge', 'Long Odds', 'Tempest',
             'Coin-Toss', 'Brinkfall', 'Wild Hunt', 'Precipice', 'Snake Eyes'],
}

TAG_ORDER = ['COMBAT', 'GATHERING', 'CRAFTING', 'ECONOMY', 'WORKORDER', 'LOOT',
             'XP', 'EXPLORATION', 'VILLAGE', 'SOCIAL', 'RISK']

RANK_BANDS = [(4, 5, 'I', 'Faint'), (6, 8, 'II', 'Rising'),
              (9, 12, 'III', 'Greater'), (13, 16, 'IV', 'Grand')]
RANK_ODDS = {'I': 0.176, 'II': 0.504, 'III': 0.301, 'IV': 0.020}

MAG_POINTS = {1: 1, 2: 2, 3: 4}
MAG_WEIGHTS = [(1, 45), (2, 37), (3, 18)]
MAG_ROMAN = {1: 'I', 2: 'II', 3: 'III'}


def rank_for(intensity):
    for lo, hi, roman, word in RANK_BANDS:
        if lo <= intensity <= hi:
            return roman, word
    return 'IV', 'Grand'


def tally_tags(picks):
    """Primary tag scores 2, each secondary scores 1."""
    score = {}
    for p in picks:
        tags = p['module']['tags']
        for i, t in enumerate(tags):
            score[t] = score.get(t, 0) + (2 if i == 0 else 1)
    return score


def choose_theme(picks):
    score = tally_tags(picks)
    if not score:
        return 'SOCIAL', score
    best = max(score.values())
    leaders = [t for t in TAG_ORDER if score.get(t, 0) == best]
    # RISK rides along on most Twists, so it never wins a tie -- but it is
    # allowed a clean plurality, which is what makes a true gambler's day.
    if len(leaders) > 1 and 'RISK' in leaders:
        leaders = [t for t in leaders if t != 'RISK']
    if len(leaders) == 1:
        return leaders[0], score
    a_primary = picks[0]['module']['tags'][0] if picks[0]['module']['tags'] else None
    if a_primary in leaders:
        return a_primary, score
    d_primary = picks[3]['module']['tags'][0] if picks[3]['module']['tags'] else None
    if d_primary in leaders:
        return d_primary, score
    return leaders[0], score


def name_event(rng, picks, theme, intensity, recent_titles=None, title_counts=None):
    """Adjective from the Twist, noun from the Theme.

    A title used in the last 100 events is redrawn. Beyond that window a repeat
    is allowed and numbered from the archive, so a returning name reads as a
    sequel rather than a bug.
    """
    recent_titles = recent_titles or set()
    title_counts = title_counts or {}
    adjectives = picks[1]['module']['adjectives']
    roman, word = rank_for(intensity)
    title = None
    for _ in range(8):
        candidate = '%s %s' % (rng.pick(adjectives), rng.pick(THEME_NOUNS[theme]))
        if candidate not in recent_titles:
            title = candidate
            break
    if title is None:
        title = candidate
    seen = title_counts.get(title, 0)
    display = title
    if seen:
        display += ' ' + ROMAN[min(seen, len(ROMAN) - 1)]
    if roman == 'IV':
        display += ' Ascendant'
    return '%s EVENT -- %s' % (theme, display), display, title, roman, word


ROMAN = ['', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X']


# ------------------------------------------------------------- coherence gate

HARD_BANS = {('B10', 'C13')}  # two competing time gates


def has_overlap(s1, s2):
    return 'GLOBAL' in s1 or 'GLOBAL' in s2 or bool(s1 & s2)


def coherent(a, b, c):
    if (b['module']['id'], c['module']['id']) in HARD_BANS:
        return False
    if not has_overlap(c['module']['surfaces'], a['module']['surfaces']):
        return False
    if not has_overlap(c['module']['surfaces'], b['module']['surfaces']):
        return False
    return True


# ------------------------------------------------------------------- rolling

def draw_slot(rng, pool, blocked):
    live = [m for m in pool if m[0] not in blocked]
    if not live:
        live = pool
    entry = rng.pick(live)
    mod = module_fields(entry)
    mag = rng.weighted(MAG_WEIGHTS)
    param = roll_param(rng, mod['param'])
    return {'module': mod, 'mag': mag, 'param': param}


def coherent_focus_pool(a, b, blocked):
    """Every Slot C module that can legally carry this Boon and Twist.

    Pre-filtering beats rejection sampling: one draw, no churn, no fallback,
    and the pool size is a directly observable health metric for the tables.
    C12 Open World is GLOBAL, so this list is never empty.
    """
    out = []
    for entry in SLOT_C:
        mod = module_fields(entry)
        if mod['id'] in blocked:
            continue
        if (b['module']['id'], mod['id']) in HARD_BANS:
            continue
        if not has_overlap(mod['surfaces'], a['module']['surfaces']):
            continue
        if not has_overlap(mod['surfaces'], b['module']['surfaces']):
            continue
        out.append(entry)
    return out or [SLOT_C[11]]


def roll_event(seed_string, blocked=None, recent_titles=None, title_counts=None):
    blocked = blocked or set()
    rng = Rng(seed_string)
    log = []

    a = draw_slot(rng, SLOT_A, blocked)
    b = draw_slot(rng, SLOT_B, blocked)

    pool = coherent_focus_pool(a, b, blocked)
    entry = rng.pick(pool)
    c = {'module': module_fields(entry), 'mag': rng.weighted(MAG_WEIGHTS),
         'param': None}
    c['param'] = roll_param(rng, c['module']['param'])
    log.append('Focus pool: %d of 20 Slot C modules reach both %s and %s.'
               % (len(pool), a['module']['id'], b['module']['id']))

    d = draw_slot(rng, SLOT_D, blocked)
    picks = [a, b, c, d]

    damped = c['module']['id'] == 'C12'
    if damped:
        # C12 has no magnitude of its own -- its three bands are the same text.
        # Leaving its roll in the intensity sum would score the mildest day of
        # the month as one of the strongest, so pin it to I before summing.
        c['mag'] = 1
        for pk in (a, b, d):
            pk['mag'] = max(1, pk['mag'] - 1)
        log.append('C12 Open World: own band pinned to I; every other module '
                   'drops one band.')

    if a['module']['id'] == 'A10' and b['module']['id'] == 'B11' and a['mag'] > 1:
        log.append('Clamp: A10 held to magnitude I beside B11, to keep a risk floor.')
        a['mag'] = 1

    intensity = sum(MAG_POINTS[pk['mag']] for pk in picks)
    theme, score = choose_theme(picks)
    full_name, display, base_title, roman, word = name_event(
        rng, picks, theme, intensity, recent_titles, title_counts)

    return {
        'seed': seed_string, 'picks': picks, 'intensity': intensity,
        'theme': theme, 'tag_score': score, 'name': full_name,
        'title': display, 'base_title': base_title, 'focus_pool': len(pool),
        'rank': roman, 'rank_word': word, 'damped': damped, 'log': log,
        'signature': '%s%d-%s%d-%s%d-%s%d' % (
            a['module']['id'], a['mag'], b['module']['id'], b['mag'],
            c['module']['id'], c['mag'], d['module']['id'], d['mag']),
    }


def is_event_day(seed_string):
    """Raw 1-in-7 gate, on its own sub-seed so the draw below is independent."""
    return Rng(seed_string + '|gate').next() < 1.0 / 7.0


DROUGHT_LIMIT = 16   # force an event after this many quiet days
STREAK_LIMIT = 2     # never a third consecutive event day


def roll_calendar(day_strings, cooldown=4, title_window=100):
    """Walk a run of server days, applying the gate, the drought floor, the
    streak ceiling, module cooldowns and title memory. Returns one entry per
    day: (day, event_or_None, reason)."""
    out = []
    quiet = 0
    streak = 0
    recent_modules = []      # list of sets, most recent last
    recent_titles = []
    title_counts = {}
    for day in day_strings:
        fire = is_event_day(day)
        reason = 'roll'
        if fire and streak >= STREAK_LIMIT:
            fire, reason = False, 'streak ceiling'
        elif not fire and quiet >= DROUGHT_LIMIT:
            fire, reason = True, 'drought floor'
        if not fire:
            quiet += 1
            streak = 0
            out.append((day, None, reason))
            continue
        blocked = set()
        for s in recent_modules[-cooldown:]:
            blocked |= s
        ev = roll_event(day, blocked, set(recent_titles[-title_window:]),
                        title_counts)
        ev['reason'] = reason
        recent_modules.append({p['module']['id'] for p in ev['picks']})
        recent_titles.append(ev['base_title'])
        title_counts[ev['base_title']] = title_counts.get(ev['base_title'], 0) + 1
        quiet = 0
        streak += 1
        out.append((day, ev, reason))
    return out


# ------------------------------------------------------------------- counting

def slot_multiplicity(pool):
    total = 0
    for entry in pool:
        mod = module_fields(entry)
        total += 3 * PARAM_COUNT[mod['param']]
    return total


def combination_counts():
    structural = (20 ** 4) * (3 ** 4)
    parameterised = 1
    for pool in (SLOT_A, SLOT_B, SLOT_C, SLOT_D):
        parameterised *= slot_multiplicity(pool)
    titles = sum(len(module_fields(e)['adjectives']) for e in SLOT_B) * \
        sum(len(v) for v in THEME_NOUNS.values())
    return structural, parameterised, titles
