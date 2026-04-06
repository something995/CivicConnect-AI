"""
Generate a richer, more diverse civic complaint dataset.

Categories (matching authority_mapping.csv and solution_knowledge_base.csv):
  - pothole_road_damage
  - garbage
  - sewage_overflow
  - waterlogging
  - streetlight_or_electricity
  - others
"""

import random
import csv
from pathlib import Path

random.seed(42)

# Resolve paths relative to project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── Hyderabad locations ──────────────────────────────────────────────
LOCATIONS = [
    "Madhapur", "Kukatpally", "Ameerpet", "LB Nagar", "Dilsukhnagar",
    "Gachibowli", "Uppal", "Secunderabad", "Mehdipatnam", "SR Nagar",
    "Begumpet", "Hitech City", "KPHB Colony", "Moosapet", "Charminar",
    "Tolichowki", "Serilingampally", "Miyapur", "Kondapur", "Manikonda",
    "Jubilee Hills", "Banjara Hills", "Tarnaka", "Habsiguda", "Malkajgiri",
    "Kompally", "Alwal", "Bowenpally", "Nagole", "Vanasthalipuram",
    "Hayathnagar", "Champapet", "Ramanthapur", "Amberpet", "Nampally",
    "Abids", "Lakdikapul", "Khairatabad", "Erragadda", "Balanagar",
    "Jeedimetla", "Chintal", "Quthbullapur", "Attapur", "Rajendranagar",
]

ROADS = [
    "main road", "colony road", "near bus stop", "market area",
    "school road", "temple street", "metro station road",
    "hospital road", "junction", "cross road", "lane",
    "highway stretch", "service road", "near signal",
    "beside flyover", "near railway crossing", "residential lane",
]

TIMES = [
    "for the last one week", "since yesterday", "for many days",
    "since the heavy rains", "for over a month", "since last night",
    "for the past few days", "from the last 2 weeks",
]

CLOSERS = [
    "Please take immediate action.",
    "This issue is causing a lot of inconvenience to residents.",
    "No one has responded even after multiple complaints.",
    "This is becoming a serious public health problem.",
    "Requesting the concerned department to resolve this urgently.",
    "People are suffering due to this negligence.",
    "This problem has been ignored for many days.",
    "Immediate repair is required.",
    "This is affecting daily commuters and pedestrians.",
    "Kindly look into this matter at the earliest.",
    "Children and elderly are at risk.",
    "This is a hazard and needs urgent attention.",
    "Please send someone to fix this soon.",
    "We have been waiting for a long time.",
    "The situation is getting worse every day.",
    "This needs to be addressed before someone gets hurt.",
]

# ── Templates per category ──────────────────────────────────────────

DATA = {
    "pothole_road_damage": {
        "templates": [
            "There is a big pothole on the {road} in {loc}.",
            "A dangerous pothole has developed on the {road} near {loc}. Vehicles are getting damaged.",
            "The road near {loc} {road} has multiple deep potholes.",
            "A huge crater has formed on the {road} in {loc}.",
            "Road surface is completely damaged near {loc} {road}.",
            "Vehicles are slipping due to a large pit on the road in {loc}.",
            "There is a deep road pit on the {road} near {loc}, causing accidents.",
            "The {road} in {loc} is in terrible condition with road damage everywhere.",
            "A big crack has appeared on the road surface near {loc} {road}.",
            "Multiple potholes on {road} in {loc}, two-wheelers are at risk.",
            "The road in {loc} near {road} is broken badly and needs urgent repair.",
            "Damaged road near {loc} is causing tire punctures and vehicle breakdowns.",
            "Due to potholes on {road} in {loc}, commuters are facing severe problems.",
            "The asphalt has completely broken on {road} near {loc}.",
            "Road condition is very poor with cuts and pits on {road} in {loc}.",
            "There are cracks and holes all over the road in {loc}, very dangerous.",
            "Potholes have formed after recent road digging near {loc} {road}.",
            "The dug up road in {loc} was never repaired, full of potholes now.",
            "Big potholes causing accidents daily on the {road} near {loc}.",
            "Road near {loc} {road} is completely uneven with bumps and pits.",
            "Huge road damage near {loc}. Bikers cannot pass safely.",
            "Road in our area {loc} is full of craters. Children can't walk safely.",
            "Construction left the road damaged near {loc} {road} and no one fixed it.",
            "Badly damaged road causing waterlogging in potholes near {loc}.",
            "Speed breakers are broken on {road} in {loc}, causing jolt to vehicles.",
        ],
    },
    "garbage": {
        "templates": [
            "There is a lot of garbage accumulated near the {road} in {loc}.",
            "Uncollected garbage has been lying near {loc} {time}.",
            "People are dumping trash openly near the {road} in {loc}.",
            "Overflowing garbage bins are creating health issues in {loc}.",
            "Bad smell coming due to uncollected waste near {loc} {road}.",
            "Garbage van has not come to {loc} {time}. Waste is piling up everywhere.",
            "Municipal garbage bin near {road} in {loc} is overflowing.",
            "Open dumping of solid waste near {loc} is attracting stray animals.",
            "Household waste is being thrown on the road near {loc} {road}.",
            "Trash and litter everywhere near {road} in {loc}. Very unhygienic.",
            "No garbage collection happening in {loc} {time}.",
            "Garbage dump near {loc} {road} is producing foul smell.",
            "Plastic waste and litter scattered all over {road} in {loc}.",
            "People are burning garbage near {loc} causing air pollution.",
            "Dustbin near {road} in {loc} has not been emptied in days.",
            "Waste materials scattered across the street in {loc}.",
            "Dead animal carcass and garbage lying near {road} in {loc}.",
            "Construction debris dumped near {road} in {loc}.",
            "Medical waste found dumped near {road} in {loc}. Health hazard!",
            "Dry and wet waste mixed together near bin at {loc} {road}.",
            "Garbage overflowing from community bin in {loc}.",
            "Piles of rubbish on {road} in {loc}, stinking badly.",
            "Waste not picked up from our colony in {loc} {time}.",
            "Filth everywhere near the market in {loc}. Garbage not cleaned.",
            "Food waste rotting on the road near {loc} {road}. Flies and mosquitoes increasing.",
        ],
    },
    "sewage_overflow": {
        "templates": [
            "Sewage is overflowing on the {road} in {loc}.",
            "Drain water is coming out on the road near {loc} {road}.",
            "Strong foul smell from the drain at {loc}.",
            "Sewage water is spreading across the {road} in {loc}.",
            "Mosquito breeding is increasing due to sewage overflow in {loc}.",
            "Open drain near {loc} {road} is overflowing and stinking.",
            "Manhole is open and sewage is leaking near {loc}.",
            "The sewage pipeline is broken near {road} in {loc}.",
            "Dirty drain water is entering homes in {loc}.",
            "Blocked drain near {loc} causing sewage to overflow on street.",
            "Sewage water flowing on {road} in {loc} {time}.",
            "Nala near {loc} is overflowing with sewage and waste water.",
            "Black dirty water from sewer on {road} in {loc}.",
            "Drain is clogged near {loc} {road}, causing backup into houses.",
            "Sewer line is burst and waste water is flowing freely in {loc}.",
            "The gutter near {road} in {loc} is blocked and overflowing.",
            "Terrible sewage smell in {loc} colony from broken sewer pipe.",
            "Wastewater from drain flooding {road} in {loc}.",
            "People cannot walk near {loc} due to sewage on {road}.",
            "Open manhole near {loc} is dangerous and sewage is leaking.",
            "Drain near {loc} {road} is blocked and sewage backing up.",
            "Residents of {loc} unable to step out due to sewage overflow.",
            "Sewage mixed with rain water on {road} near {loc}.",
            "Sewer overflowing near school in {loc}. Very unhygienic for children.",
            "Underground drainage system failed in {loc}, sewage everywhere.",
        ],
    },
    "waterlogging": {
        "templates": [
            "Severe waterlogging on {road} in {loc} after rain.",
            "Water is stagnating on the {road} near {loc} {time}.",
            "Flooding in {loc} colony due to poor drainage system.",
            "Water not draining from {road} in {loc} even hours after rain.",
            "Roads submerged in water in {loc}. Vehicles stuck.",
            "Rain water accumulating on {road} near {loc}. No outlet.",
            "Low-lying area in {loc} gets flooded every time it rains.",
            "Stagnant water breeding mosquitoes near {road} in {loc}.",
            "Waterlogging near {loc} {road} is causing traffic problems.",
            "After every rain, {road} in {loc} turns into a pond.",
            "Storm water drain is blocked near {loc}, causing flooding.",
            "Ankle-deep water on {road} in {loc} {time}.",
            "Water entering homes in {loc} due to waterlogging.",
            "Vehicles submerged due to heavy waterlogging in {loc}.",
            "Children cannot go to school due to waterlogging near {loc}.",
            "Rain water flooding {road} in {loc}, two-wheelers cannot pass.",
            "Water stagnation near {loc} {road} for many days creating foul smell.",
            "Waterlogged area near {loc} becoming breeding ground for mosquitoes.",
            "Flooded street in {loc} due to choked drainage.",
            "No proper drainage in {loc}, every rain causes water accumulation.",
            "Rainwater not receding from {road} near {loc}.",
            "Standing water on {road} in {loc} causing dengue fear.",
            "Knee-deep water in {loc} locality after yesterday's rain.",
            "Water submerged road near {loc} {road} is impassable.",
            "Puddles and water stagnation everywhere on {road} in {loc}.",
        ],
    },
    "streetlight_or_electricity": {
        "templates": [
            "The street light near {loc} {road} is not functioning.",
            "Several street lights are not working in {loc}.",
            "There is complete darkness at night due to faulty street light in {loc}.",
            "The broken light pole near {loc} is unsafe for pedestrians.",
            "Street light has been switched off for many days in {loc}.",
            "Road is very dark at {loc} {road} because street light is dead.",
            "Electric wires are hanging dangerously near {road} in {loc}.",
            "Sparking from electric pole near {loc} {road}. Very dangerous!",
            "Power outage in {loc} {time}. No electricity in the area.",
            "Street lamp near {road} in {loc} is flickering and not stable.",
            "No street lighting on entire {road} stretch in {loc}.",
            "Transformer near {loc} is sparking at night. Fire hazard.",
            "Electric pole is tilted near {road} in {loc}. Could fall anytime.",
            "Bulb fused in street light near {loc} {road}. Not replaced.",
            "Night time visibility is zero on {road} near {loc}. No lights.",
            "All lights in {loc} colony are not working {time}.",
            "Electricity cable fallen on road near {loc}. Very risky.",
            "LED street light installed but never turned on in {loc}.",
            "Frequent power cuts in {loc} area {time}.",
            "Light pole damaged by accident near {road} in {loc}. Not repaired.",
            "Street lamps in {loc} are all off. Women feel unsafe at night.",
            "No illumination on {road} in {loc}, accidents happening regularly.",
            "Electricity wire touching tree near {loc} {road}, sparks visible.",
            "Street light timer fault in {loc}, lights turn off at 9 PM itself.",
            "High tension wire hanging low near {road} in {loc}. Extremely dangerous.",
        ],
    },
    "others": {
        "templates": [
            "Stray dogs are attacking people near {road} in {loc}.",
            "Illegal construction happening near {loc} {road}.",
            "Noise pollution from loudspeaker near {loc} {time}.",
            "Footpath encroachment by vendors near {road} in {loc}.",
            "Public toilet near {loc} {road} is not maintained.",
            "Tree has fallen on the road near {loc} {road}.",
            "Unauthorized parking blocking {road} in {loc}.",
            "Road divider broken near {road} in {loc}.",
            "Traffic signal not working at {loc} junction.",
            "Mosquito fogging needed in {loc} colony urgently.",
            "Park in {loc} is not maintained, becoming unsafe.",
            "Water tanker not coming to {loc} {time}.",
            "Bus stop shelter damaged near {loc} {road}.",
            "Auto drivers overcharging passengers near {loc}.",
            "Drinking water supply issue in {loc} {time}.",
            "Abandoned vehicle blocking road near {loc} {road}.",
            "Damaged bench in public park near {loc}.",
            "Speed breaker needed urgently on {road} in {loc}.",
            "Stray cattle roaming on {road} in {loc}.",
            "Public tap running and wasting water near {loc} {road}.",
            "Open well near {loc} {road} is dangerous for kids.",
            "No pedestrian crossing at busy {road} in {loc}.",
            "Smoke and dust from construction site near {loc}.",
            "Boundary wall collapsed near {road} in {loc}.",
            "Graffiti and vandalism on public property in {loc}.",
        ],
    },
}


def generate_scripts(label, count):
    scripts = set()
    templates = DATA[label]["templates"]
    while len(scripts) < count:
        template = random.choice(templates)
        loc = random.choice(LOCATIONS)
        road = random.choice(ROADS)
        time = random.choice(TIMES)
        closer = random.choice(CLOSERS)

        text = template.format(loc=loc, road=road, time=time)
        text = f"{text} {closer}"
        scripts.add((text, label))
    return list(scripts)


# Generate balanced dataset
dataset = []
PER_CLASS = 350  # 350 per class x 6 = 2100 total

for issue in DATA.keys():
    dataset.extend(generate_scripts(issue, PER_CLASS))

random.shuffle(dataset)

with open(PROJECT_ROOT / "data" / "civic_complaint_scripts_1000.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["text", "label"])
    writer.writerows(dataset)

print(f"✅ Generated {len(dataset)} complaint records across {len(DATA)} categories")
for label in DATA:
    count = sum(1 for _, l in dataset if l == label)
    print(f"   {label}: {count}")
