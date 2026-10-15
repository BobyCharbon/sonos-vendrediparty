"""Cuisine : plats du monde, fromages, boissons, vins, ingrédients, cocktails, techniques et vocabulaire."""

from . import make, pick
from .fr import bare, de
from .gen_geo import COUNTRIES

FR, CH, IT, ES, JP, US = "France", "Suisse", "Italie", "Espagne", "Japon", "États-Unis"
DISHES = [
    ("le cassoulet", FR), ("la bouillabaisse", FR), ("le bœuf bourguignon", FR), ("la quiche lorraine", FR), ("la ratatouille", FR), ("la tartiflette", FR),
    ("le coq au vin", FR), ("la crème brûlée", FR), ("le croque-monsieur", FR), ("la blanquette de veau", FR), ("le gratin dauphinois", FR),
    ("la galette bretonne", FR), ("le pot-au-feu", FR), ("la soupe à l'oignon", FR), ("les macarons", FR), ("le kouign-amann", FR), ("la tarte Tatin", FR),
    ("le clafoutis", FR), ("la salade niçoise", FR), ("l'aligot", FR), ("la socca", FR), ("le cannelé", FR), ("le paris-brest", FR), ("les crêpes Suzette", FR),
    ("la fondue moitié-moitié", CH), ("la raclette", CH), ("les röstis", CH), ("l'émincé de veau à la zurichoise", CH), ("le papet vaudois", CH),
    ("la tarte au vin cuit", CH), ("les malakoffs", CH), ("la croûte au fromage", CH), ("les älplermagronen", CH), ("le birchermüesli", CH),
    ("les leckerlis", CH), ("le gâteau du Vully", CH), ("la cuchaule", CH), ("le cholera (tourte valaisanne)", CH), ("les capuns", CH), ("les pizokels", CH),
    ("le saucisson vaudois", CH), ("le cervelas", CH), ("la meringue à la double-crème", CH), ("la tourte au kirsch de Zoug", CH), ("la tourte aux noix des Grisons", CH),
    ("la pizza margherita", IT), ("le risotto alla milanese", IT), ("les lasagnes", IT), ("le tiramisu", IT), ("l'osso buco", IT), ("les spaghettis carbonara", IT),
    ("le pesto alla genovese", IT), ("la panna cotta", IT), ("le vitello tonnato", IT), ("les arancini", IT), ("les gnocchis", IT), ("le minestrone", IT),
    ("la focaccia", IT), ("le carpaccio", IT), ("la piadina", IT), ("les cannoli", IT),
    ("la paella", ES), ("le gaspacho", ES), ("la tortilla de patatas", ES), ("les churros", ES), ("le jambon ibérique", ES), ("le pulpo a la gallega", ES),
    ("la crème catalane", ES), ("la fabada asturiana", ES),
    ("le pastel de nata", "Portugal"), ("le bacalhau à brás", "Portugal"), ("la francesinha", "Portugal"), ("le caldo verde", "Portugal"),
    ("la moussaka", "Grèce"), ("le tzatziki", "Grèce"), ("le souvlaki", "Grèce"), ("la spanakopita", "Grèce"), ("le gyros", "Grèce"),
    ("le döner kebab", "Turquie"), ("le loukoum", "Turquie"), ("l'ayran", "Turquie"), ("le simit", "Turquie"), ("le lahmacun", "Turquie"),
    ("le taboulé", "Liban"), ("le fattouch", "Liban"), ("le kebbé", "Liban"),
    ("le tajine", "Maroc"), ("la pastilla", "Maroc"), ("la harira", "Maroc"), ("les cornes de gazelle", "Maroc"), ("la brick", "Tunisie"), ("la harissa", "Tunisie"),
    ("l'injera", "Éthiopie"), ("le bobotie", "Afrique du Sud"), ("le biltong", "Afrique du Sud"), ("le thiéboudiène", "Sénégal"), ("le yassa", "Sénégal"),
    ("l'attiéké", "Côte d'Ivoire"),
    ("le butter chicken", "Inde"), ("le biryani", "Inde"), ("le naan", "Inde"), ("le dal", "Inde"), ("les samoussas", "Inde"), ("le poulet tandoori", "Inde"),
    ("le lassi", "Inde"),
    ("le canard laqué", "Chine"), ("les dim sum", "Chine"), ("le porc aigre-doux", "Chine"), ("le riz cantonais", "Chine"), ("le mapo tofu", "Chine"),
    ("les jiaozi", "Chine"), ("la fondue chinoise (hot pot)", "Chine"),
    ("les sushis", JP), ("les ramen", JP), ("le tempura", JP), ("les gyozas", JP), ("la soupe miso", JP), ("les onigiris", JP), ("l'okonomiyaki", JP),
    ("les mochis", JP), ("le bœuf de Kobe (wagyu)", JP), ("le sashimi", JP), ("les takoyakis", JP), ("les yakitoris", JP),
    ("le kimchi", "Corée du Sud"), ("le bibimbap", "Corée du Sud"), ("le bulgogi", "Corée du Sud"), ("les tteokbokki", "Corée du Sud"),
    ("le pad thaï", "Thaïlande"), ("le tom yum", "Thaïlande"), ("le curry vert", "Thaïlande"), ("le som tam", "Thaïlande"), ("le riz gluant à la mangue", "Thaïlande"),
    ("le phở", "Viêt Nam"), ("les nems", "Viêt Nam"), ("le bánh mì", "Viêt Nam"), ("le bún bò", "Viêt Nam"),
    ("le nasi goreng", "Indonésie"), ("le rendang", "Indonésie"), ("le gado-gado", "Indonésie"),
    ("les tacos", "Mexique"), ("le guacamole", "Mexique"), ("les enchiladas", "Mexique"), ("les quesadillas", "Mexique"), ("le mole poblano", "Mexique"),
    ("les nachos", "Mexique"), ("le pozole", "Mexique"),
    ("le hamburger", US), ("le hot-dog", US), ("les brownies", US), ("le cheesecake new-yorkais", US), ("les pancakes", US), ("le clam chowder", US),
    ("le cornbread", US), ("les donuts", US), ("le mac and cheese", US), ("le pulled pork", US), ("la key lime pie", US), ("le poké", US),
    ("la poutine", "Canada"), ("le sirop d'érable", "Canada"), ("la tourtière", "Canada"), ("le pouding chômeur", "Canada"),
    ("la feijoada", "Brésil"), ("le pão de queijo", "Brésil"), ("la moqueca", "Brésil"), ("les brigadeiros", "Brésil"),
    ("l'asado", "Argentine"), ("les empanadas", "Argentine"), ("le dulce de leche", "Argentine"), ("le chimichurri", "Argentine"),
    ("le ceviche", "Pérou"), ("le lomo saltado", "Pérou"),
    ("le fish and chips", "Royaume-Uni"), ("le pudding de Noël", "Royaume-Uni"), ("le full English breakfast", "Royaume-Uni"), ("le shepherd's pie", "Royaume-Uni"),
    ("les scones", "Royaume-Uni"), ("le haggis", "Royaume-Uni"), ("le Yorkshire pudding", "Royaume-Uni"), ("le crumble", "Royaume-Uni"),
    ("l'irish stew", "Irlande"), ("le soda bread", "Irlande"),
    ("les moules-frites", "Belgique"), ("la carbonade flamande", "Belgique"), ("les gaufres de Liège", "Belgique"), ("le waterzooi", "Belgique"),
    ("les chicons au gratin", "Belgique"),
    ("les stroopwafels", "Pays-Bas"), ("les bitterballen", "Pays-Bas"), ("le hareng cru (haring)", "Pays-Bas"),
    ("la currywurst", "Allemagne"), ("la forêt-noire", "Allemagne"), ("le stollen", "Allemagne"), ("le sauerbraten", "Allemagne"), ("les spätzle", "Allemagne"),
    ("l'escalope viennoise", "Autriche"), ("l'apfelstrudel", "Autriche"), ("la sachertorte", "Autriche"), ("le kaiserschmarrn", "Autriche"),
    ("le goulasch", "Hongrie"), ("le lángos", "Hongrie"), ("les pierogi", "Pologne"), ("le bigos", "Pologne"),
    ("le bœuf Stroganoff", "Russie"), ("les blinis", "Russie"), ("les pelmenis", "Russie"),
    ("les köttbullar", "Suède"), ("le gravlax", "Suède"), ("les kanelbullar", "Suède"), ("le smörgåsbord", "Suède"), ("le surströmming", "Suède"),
    ("le smørrebrød", "Danemark"), ("les æbleskiver", "Danemark"), ("le brunost", "Norvège"), ("la tourte carélienne", "Finlande"), ("le skyr", "Islande"),
    ("le hákarl", "Islande"), ("le khachapuri", "Géorgie"), ("le ghormeh sabzi", "Iran"), ("la Vegemite", "Australie"), ("les lamingtons", "Australie"),
    ("le poulet jerk", "Jamaïque"), ("la ropa vieja", "Cuba"),
]
FAMOUS_DISHES = {"la pizza margherita", "les sushis", "la paella", "la fondue moitié-moitié", "la raclette", "le hamburger", "les tacos", "le pad thaï",
                 "la moussaka", "le tajine", "le fish and chips", "la poutine", "les röstis", "le tiramisu", "les moules-frites", "le goulasch",
                 "le kimchi", "le phở", "le canard laqué", "le croque-monsieur", "le gaspacho", "l'escalope viennoise", "le guacamole"}

# Plats suisses → canton (pour le thème Suisse)
SWISS_DISHES = [
    ("le papet vaudois", "Vaud"), ("le saucisson vaudois", "Vaud"), ("le taillé aux greubons", "Vaud"), ("la raclette (AOP)", "Valais"),
    ("le cholera", "Valais"), ("le pain de seigle (AOP)", "Valais"), ("la cuchaule", "Fribourg"), ("la soupe de chalet", "Fribourg"),
    ("la meringue à la double-crème", "Fribourg"), ("le gâteau du Vully", "Fribourg"), ("les capuns", "Grisons"), ("les pizokels", "Grisons"),
    ("la viande des Grisons", "Grisons"), ("la tourte aux noix engadinoise", "Grisons"), ("l'émincé à la zurichoise", "Zurich"),
    ("les leckerlis", "Bâle-Ville"), ("la soupe à la farine bâloise", "Bâle-Ville"), ("la tourte au kirsch", "Zoug"), ("le Rüeblitorte (gâteau aux carottes)", "Argovie"),
    ("les biberli", "Appenzell Rhodes-Intérieures"), ("les filets de perche", "Genève"), ("la longeole", "Genève"), ("la saucisse aux choux", "Vaud"),
    ("la toétché", "Jura"), ("la damassine (eau-de-vie)", "Jura"), ("la tête de moine", "Berne"), ("le risotto aux bolets", "Tessin"),
    ("la polenta et le brasato", "Tessin"), ("la torta di pane", "Tessin"), ("la saucisse de Saint-Gall", "Saint-Gall"), ("l'absinthe du Val-de-Travers", "Neuchâtel"),
    ("le Luzerner Chügelipastete", "Lucerne"),
]

# Fromage → pays
CHEESES = [
    ("le gruyère", CH), ("l'emmental", CH), ("le vacherin fribourgeois", CH), ("la tête de moine", CH), ("l'appenzeller", CH), ("le sbrinz", CH),
    ("l'Etivaz", CH), ("la tomme vaudoise", CH), ("la raclette du Valais", CH),
    ("le camembert", FR), ("le roquefort", FR), ("le brie de Meaux", FR), ("le comté", FR), ("le reblochon", FR), ("le beaufort", FR), ("le munster", FR),
    ("le saint-nectaire", FR), ("le cantal", FR), ("l'époisses", FR), ("le morbier", FR), ("le bleu d'Auvergne", FR), ("le pont-l'évêque", FR),
    ("le livarot", FR), ("le chaource", FR), ("l'ossau-iraty", FR), ("la tomme de Savoie", FR), ("le crottin de Chavignol", FR), ("le sainte-maure", FR),
    ("le rocamadour", FR), ("le neufchâtel (normand)", FR),
    ("le parmesan (parmigiano reggiano)", IT), ("la mozzarella", IT), ("le gorgonzola", IT), ("le pecorino romano", IT), ("le mascarpone", IT),
    ("la ricotta", IT), ("le taleggio", IT), ("le grana padano", IT), ("la burrata", IT), ("la fontina", IT), ("l'asiago", IT), ("le provolone", IT),
    ("le manchego", ES), ("le cabrales", ES), ("l'idiazábal", ES), ("le mahón", ES),
    ("la feta", "Grèce"), ("le kefalotyri", "Grèce"), ("l'halloumi", "Chypre"), ("le gouda", "Pays-Bas"), ("l'edam", "Pays-Bas"), ("le leerdammer", "Pays-Bas"),
    ("le cheddar", "Royaume-Uni"), ("le stilton", "Royaume-Uni"), ("le wensleydale", "Royaume-Uni"), ("le red leicester", "Royaume-Uni"),
    ("le danablu", "Danemark"), ("le havarti", "Danemark"), ("le fromage de Herve", "Belgique"), ("le maredsous", "Belgique"),
    ("le serra da estrela", "Portugal"), ("le queso Oaxaca", "Mexique"),
]
CHEESE_MILK = [("le roquefort", "Brebis"), ("le pecorino romano", "Brebis"), ("le manchego", "Brebis"), ("l'ossau-iraty", "Brebis"),
               ("le crottin de Chavignol", "Chèvre"), ("le sainte-maure", "Chèvre"), ("le rocamadour", "Chèvre"), ("la mozzarella di bufala", "Bufflonne"),
               ("le gruyère", "Vache"), ("le comté", "Vache"), ("l'emmental", "Vache"), ("le camembert", "Vache"), ("le reblochon", "Vache"), ("le parmesan", "Vache")]
SWISS_CHEESES = [("le gruyère", "Fribourg"), ("l'emmental", "Berne"), ("l'appenzeller", "Appenzell Rhodes-Intérieures"), ("le vacherin fribourgeois", "Fribourg"),
                 ("l'Etivaz", "Vaud"), ("la raclette du Valais", "Valais"), ("la tomme vaudoise", "Vaud"), ("le formaggio d'alpe ticinese", "Tessin")]

DRINKS = [
    ("le saké", JP), ("l'ouzo", "Grèce"), ("le raki", "Turquie"), ("la tequila", "Mexique"), ("le mezcal", "Mexique"), ("la cachaça", "Brésil"),
    ("le bourbon", US), ("le porto", "Portugal"), ("la sangria", ES), ("le limoncello", IT), ("la grappa", IT), ("le Rivella", CH), ("l'Ovomaltine", CH),
    ("la Guinness", "Irlande"), ("le champagne", FR), ("le cava", ES), ("le prosecco", IT), ("l'Aperol", IT), ("le Campari", IT), ("le Jägermeister", "Allemagne"),
    ("le soju", "Corée du Sud"), ("le baijiu", "Chine"), ("le pastis", FR), ("le calvados", FR), ("le cognac", FR), ("l'armagnac", FR), ("la chartreuse", FR),
    ("le Fernet-Branca", IT), ("le Pimm's", "Royaume-Uni"), ("le kvas", "Russie"), ("le rooibos", "Afrique du Sud"), ("le maté", "Argentine"),
    ("le matcha", JP), ("la caipirinha", "Brésil"), ("le mojito", "Cuba"), ("le lassi", "Inde"), ("le whisky écossais (scotch)", "Royaume-Uni"),
]
WINE_REGIONS = [("Bordeaux", FR), ("la Bourgogne", FR), ("la Champagne", FR), ("la Rioja", ES), ("le Chianti", IT), ("le Barolo (Piémont)", IT),
                ("Lavaux", CH), ("la Napa Valley", US), ("Mendoza", "Argentine"), ("la vallée du Douro", "Portugal"), ("la Moselle allemande", "Allemagne"),
                ("Tokaj", "Hongrie"), ("la Barossa Valley", "Australie"), ("Marlborough", "Nouvelle-Zélande"), ("Stellenbosch", "Afrique du Sud"),
                ("le Valais (Fendant, Petite Arvine)", CH), ("la vallée de Colchagua", "Chili"), ("la Wachau", "Autriche")]

# Spécialité française → région (provinces traditionnelles)
FR_REGIONS = [
    ("la choucroute", "Alsace"), ("le baeckeoffe", "Alsace"), ("le kouglof", "Alsace"), ("la flammekueche (tarte flambée)", "Alsace"), ("le munster", "Alsace"),
    ("la quiche", "Lorraine"), ("la potée lorraine", "Lorraine"), ("les madeleines de Commercy", "Lorraine"), ("la mirabelle", "Lorraine"),
    ("le kouign-amann", "Bretagne"), ("les galettes de sarrasin", "Bretagne"), ("le far breton", "Bretagne"), ("le cidre et le chouchen", "Bretagne"),
    ("le camembert", "Normandie"), ("le calvados", "Normandie"), ("la teurgoule", "Normandie"), ("les tripes à la mode de Caen", "Normandie"),
    ("la bouillabaisse", "Provence"), ("la tapenade", "Provence"), ("l'aïoli", "Provence"), ("les calissons", "Provence"), ("la ratatouille", "Provence"),
    ("la tartiflette", "Savoie"), ("la fondue savoyarde", "Savoie"), ("le reblochon", "Savoie"), ("la croziflette (crozets)", "Savoie"),
    ("le bœuf bourguignon", "Bourgogne"), ("les escargots au beurre persillé", "Bourgogne"), ("le kir", "Bourgogne"), ("la moutarde de Dijon", "Bourgogne"),
    ("la quenelle", "Lyon (Lyonnais)"), ("le tablier de sapeur", "Lyon (Lyonnais)"), ("la cervelle de canut", "Lyon (Lyonnais)"), ("les bugnes", "Lyon (Lyonnais)"),
    ("l'aligot", "Auvergne"), ("la truffade", "Auvergne"), ("le saint-nectaire", "Auvergne"), ("la potée auvergnate", "Auvergne"),
    ("le gâteau basque", "Pays basque"), ("le piment d'Espelette", "Pays basque"), ("la piperade", "Pays basque"), ("le jambon de Bayonne", "Pays basque"),
    ("le foie gras", "Périgord"), ("le confit de canard", "Périgord"), ("les noix du Périgord", "Périgord"),
    ("le cassoulet", "Languedoc"), ("la brandade de Nîmes", "Languedoc"), ("le pélardon", "Languedoc"),
    ("le welsh", "Nord"), ("le potjevleesch", "Nord"), ("la carbonade", "Nord"), ("le maroilles", "Nord"),
    ("le brocciu", "Corse"), ("le figatellu", "Corse"), ("le fiadone", "Corse"),
    ("la socca", "Nice (Comté de Nice)"), ("la pissaladière", "Nice (Comté de Nice)"), ("la salade niçoise", "Nice (Comté de Nice)"),
    ("le canelé", "Bordelais"), ("l'entrecôte bordelaise", "Bordelais"), ("le comté", "Franche-Comté"), ("la saucisse de Morteau", "Franche-Comté"),
    ("le vin jaune", "Franche-Comté"), ("les rillettes du Mans", "Maine"), ("les bêtises de Cambrai", "Nord"), ("la tarte Tatin", "Sologne"),
]

# Plat → ingrédient principal
INGREDIENTS = [
    ("le guacamole", "L'avocat"), ("le houmous", "Les pois chiches"), ("le gaspacho", "La tomate"), ("le pesto", "Le basilic"), ("la tapenade", "Les olives"),
    ("le baba ganoush", "L'aubergine"), ("le risotto", "Le riz"), ("la polenta", "La semoule de maïs"), ("le tofu", "Le soja"), ("la paella", "Le riz"),
    ("les röstis", "Les pommes de terre"), ("le tiramisu", "Le mascarpone"), ("la mayonnaise", "Le jaune d'œuf et l'huile"), ("la béchamel", "Le lait, le beurre et la farine"),
    ("l'aïoli", "L'ail"), ("la meringue", "Les blancs d'œufs et le sucre"), ("les macarons", "La poudre d'amande"), ("la frangipane", "La poudre d'amande"),
    ("le nougat", "Le miel et les amandes"), ("la ganache", "Le chocolat et la crème"), ("la chantilly", "La crème fouettée"), ("le gravlax", "Le saumon"),
    ("le ceviche", "Le poisson cru"), ("le cassoulet", "Les haricots blancs"), ("la choucroute", "Le chou fermenté"), ("le taboulé libanais", "Le persil"),
    ("le miso", "Le soja fermenté"), ("le seitan", "Le gluten de blé"), ("le cidre", "La pomme"), ("le poiré", "La poire"), ("le kirsch", "La cerise"),
    ("le saké", "Le riz"), ("la tequila", "L'agave"), ("le rhum", "La canne à sucre"), ("le gin", "Les baies de genièvre"), ("la bière", "L'orge maltée"),
    ("le pudding de riz", "Le riz"), ("la ratatouille", "Les légumes d'été (aubergine, courgette, poivron, tomate)"), ("la soupe à l'oignon", "L'oignon"),
    ("le chili con carne", "La viande hachée et les haricots rouges"), ("le dal", "Les lentilles"), ("le tzatziki", "Le yaourt et le concombre"),
    ("le pain perdu", "Le pain rassis"), ("les frites", "Les pommes de terre"), ("le popcorn", "Le maïs"), ("le tapioca", "Le manioc"),
    ("le chocolat", "Le cacao"), ("le café", "Les grains de caféier"), ("le thé", "Les feuilles de théier"), ("le beurre", "La crème"),
    ("le yaourt", "Le lait fermenté"), ("le ketchup", "La tomate"), ("la moutarde", "Les graines de moutarde"), ("le wasabi", "Le raifort japonais"),
    ("le pesto rosso", "La tomate séchée"), ("la soupe miso", "La pâte de soja fermentée"), ("le caviar", "Les œufs d'esturgeon"), ("le tarama", "Les œufs de poisson (cabillaud)"),
    ("les escargots de Bourgogne", "Les escargots et le beurre persillé"), ("le foie gras", "Le foie de canard ou d'oie"), ("la pâte d'amande (massepain)", "Les amandes et le sucre"),
    ("le praliné", "Les noisettes ou amandes caramélisées"), ("le gianduja", "Le chocolat et la noisette"), ("le lemon curd", "Le citron"),
]

COCKTAILS = [("Mojito", "Le rhum"), ("Caipirinha", "La cachaça"), ("Margarita", "La tequila"), ("Piña colada", "Le rhum"), ("Bloody Mary", "La vodka"),
             ("Cosmopolitan", "La vodka"), ("Moscow mule", "La vodka"), ("Negroni", "Le gin"), ("Gin tonic", "Le gin"), ("Daïquiri", "Le rhum"),
             ("Cuba libre", "Le rhum"), ("Tequila sunrise", "La tequila"), ("Old Fashioned", "Le whisky (bourbon)"), ("Manhattan", "Le whisky"),
             ("Mai Tai", "Le rhum"), ("White Russian", "La vodka"), ("Dry Martini", "Le gin"), ("Kir royal", "Le champagne"), ("Paloma", "La tequila"),
             ("Mint julep", "Le whisky (bourbon)"), ("Whisky sour", "Le whisky"), ("Pisco sour", "Le pisco"), ("Spritz", "L'Aperol et le prosecco"),
             ("Irish coffee", "Le whisky irlandais")]
BASES = ["Le rhum", "La vodka", "Le gin", "La tequila", "Le whisky", "La cachaça", "Le cognac", "Le pisco"]

WRITTEN = [
    (1, "Quel fruit sert à faire le guacamole ?", "L'avocat", ["La mangue", "Le kiwi", "La pomme"]),
    (1, "Quel ustensile sert à fouetter les blancs en neige ?", "Le fouet", ["La louche", "L'écumoire", "La mandoline"]),
    (2, "À quoi sert une mandoline en cuisine ?", "À trancher finement les légumes", ["À battre les œufs", "À filtrer une sauce", "À peser les ingrédients"]),
    (2, "À quoi sert un chinois en cuisine ?", "À filtrer les sauces", ["À couper les légumes", "À cuire à la vapeur", "À râper le fromage"]),
    (2, "Dans quoi cuit-on traditionnellement le couscous à la vapeur ?", "Un couscoussier", ["Un wok", "Une cocotte-minute", "Un tajine"]),
    (2, "Quel récipient en terre cuite donne son nom à un plat marocain ?", "Le tajine", ["Le couscoussier", "Le caquelon", "La marmite"]),
    (2, "Comment s'appelle le récipient de la fondue au fromage ?", "Le caquelon", ["La raclonette", "Le poêlon à frire", "La cocotte"]),
    (2, "Quelle poêle bombée est utilisée en cuisine asiatique ?", "Le wok", ["La sauteuse", "La crêpière", "La paella"]),
    (2, "Quel est le nom de la poêle large et plate de la paella ?", "La paella (paellera)", ["Le wok", "La sauteuse", "Le tajine"]),
    (2, "Quelle température atteint environ un four à pizza napolitain traditionnel ?", "Environ 450 °C", ["Environ 200 °C", "Environ 300 °C", "Environ 600 °C"]),
    (2, "À combien de degrés bout l'eau dans une cocotte-minute (environ) ?", "120 °C", ["100 °C", "90 °C", "150 °C"]),
    (2, "Quel fruit est utilisé pour faire le cidre ?", "La pomme", ["La poire", "Le raisin", "La prune"]),
    (2, "Avec quelles céréales fait-on traditionnellement le whisky écossais ?", "L'orge maltée", ["Le maïs", "Le seigle", "Le riz"]),
    (2, "Quelle céréale est majoritaire dans le bourbon américain ?", "Le maïs", ["L'orge", "Le blé", "Le seigle"]),
    (2, "Quel fruit rouge sert à faire le kir ?", "Le cassis", ["La framboise", "La fraise", "La groseille"]),
    (2, "Quel apéritif anisé est populaire à Marseille ?", "Le pastis", ["L'ouzo", "Le raki", "L'absinthe"]),
    (2, "Quelle plante donne son goût à l'absinthe ?", "L'armoise absinthe", ["La verveine", "La menthe", "La gentiane"]),
    (2, "Dans quelle vallée neuchâteloise l'absinthe est-elle née ?", "Le Val-de-Travers", ["Le Val-de-Ruz", "La vallée de Joux", "La vallée de la Brévine"]),
    (2, "Quel est le cépage blanc le plus cultivé en Suisse ?", "Le chasselas", ["Le riesling", "La petite arvine", "Le chardonnay"]),
    (2, "Comment appelle-t-on le chasselas en Valais ?", "Le fendant", ["Le dézaley", "Le perlan", "Le johannisberg"]),
    (2, "Quel cépage rouge est roi au Tessin ?", "Le merlot", ["Le pinot noir", "Le gamay", "La syrah"]),
    (2, "Quel vin rosé de Neuchâtel porte un nom d'oiseau ?", "L'œil-de-perdrix", ["Le pinot gris", "Le cornalin", "Le humagne"]),
    (2, "Quelle région viticole vaudoise en terrasses est classée à l'UNESCO ?", "Lavaux", ["La Côte", "Le Chablais", "Les Côtes de l'Orbe"]),
    (2, "Quelle fête du vin a lieu environ tous les 20 à 25 ans à Vevey ?", "La Fête des Vignerons", ["La Fête des Vendanges", "La Bénichon", "Le Comptoir suisse"]),
    (2, "Quelle fête de la récolte, avec un menu de sept plats, est typique de Fribourg ?", "La Bénichon", ["La Fête des Vignerons", "L'Escalade", "La Saint-Martin"]),
    (2, "Quelle sauce verte d'Argentine accompagne l'asado ?", "Le chimichurri", ["Le pesto", "La salsa verde mexicaine", "Le guacamole"]),
    (2, "Quelle sauce piquante tunisienne est à base de piments ?", "La harissa", ["Le ras-el-hanout", "Le zaatar", "Le sumac"]),
    (2, "Quel mélange d'épices marocain signifie « tête de l'épicerie » ?", "Le ras-el-hanout", ["Le garam masala", "Le zaatar", "Le cinq-épices"]),
    (2, "Quel mélange d'épices est typique de la cuisine indienne ?", "Le garam masala", ["Le ras-el-hanout", "Les herbes de Provence", "Le zaatar"]),
    (2, "Quel fruit à coque sert à faire le pesto alla genovese ?", "Le pignon de pin", ["La noix", "L'amande", "La noisette"]),
    (2, "Quel légume est la star de la vichyssoise ?", "Le poireau (avec la pomme de terre)", ["La carotte", "Le chou-fleur", "Le céleri"]),
    (1, "Botaniquement, la tomate est…", "Un fruit", ["Un légume", "Une racine", "Une graine"]),
    (1, "De quelle couleur est l'intérieur d'un kiwi ?", "Vert", ["Orange", "Rouge", "Blanc"]),
    (1, "Quel légume fait pleurer quand on le coupe ?", "L'oignon", ["La carotte", "Le poireau", "Le céleri"]),
    (2, "Quelle épice, la plus chère du monde, vient du pistil d'une fleur ?", "Le safran", ["La vanille", "La cardamome", "Le curcuma"]),
    (2, "De quelle plante vient la vanille ?", "D'une orchidée", ["D'un palmier", "D'un arbuste à baies", "D'une liane de poivre"]),
    (2, "Quelle épice jaune colore le curry ?", "Le curcuma", ["Le safran", "Le paprika", "Le cumin"]),
    (2, "Le paprika est fait à partir de…", "Piments ou poivrons séchés", ["Tomates séchées", "Graines de coriandre", "Racines de curcuma"]),
    (2, "De quel arbre vient la cannelle ?", "De l'écorce du cannelier", ["Du fruit du muscadier", "Des feuilles du laurier", "Des racines du gingembre"]),
    (2, "Le clou de girofle est…", "Un bouton de fleur séché", ["Une graine", "Une racine", "Une écorce"]),
    (2, "Quelle herbe aromatique est la base du pesto ?", "Le basilic", ["Le persil", "La coriandre", "La menthe"]),
    (2, "Quelle herbe divise le monde : on l'adore ou on lui trouve un goût de savon ?", "La coriandre", ["Le persil", "L'aneth", "Le basilic"]),
    (2, "Que signifie « al dente » ?", "Cuit mais encore un peu ferme", ["Très cuit", "Cru", "Cuit à la vapeur"]),
    (2, "Que veut dire « blanchir » un légume ?", "Le plonger rapidement dans l'eau bouillante", ["Le peler", "Le faire mariner", "Le faire dorer au four"]),
    (2, "Comment s'appelle une découpe en fins bâtonnets ?", "La julienne", ["La brunoise", "La mirepoix", "La chiffonnade"]),
    (2, "Comment s'appelle une découpe en tout petits dés ?", "La brunoise", ["La julienne", "La chiffonnade", "Les cubes"]),
    (2, "Comment s'appelle la découpe de feuilles en fines lanières ?", "La chiffonnade", ["La julienne", "La brunoise", "La paysanne"]),
    (2, "Comment s'appelle la cuisson lente dans une poche sous vide à basse température ?", "La cuisson sous vide", ["La cuisson à l'étouffée", "Le pochage", "Le braisage"]),
    (2, "Comment s'appelle un bouillon clarifié ?", "Un consommé", ["Un velouté", "Une bisque", "Une soupe"]),
    (2, "Comment s'appelle une soupe de crustacés ?", "Une bisque", ["Un consommé", "Un velouté", "Une garbure"]),
    (2, "Quelle sauce mère est faite d'un roux et de lait ?", "La béchamel", ["La hollandaise", "La mayonnaise", "La sauce tomate"]),
    (2, "Quelle sauce est faite de jaunes d'œufs et de beurre clarifié, avec du citron ?", "La hollandaise", ["La béarnaise", "La mayonnaise", "La béchamel"]),
    (2, "Quelle herbe distingue la sauce béarnaise ?", "L'estragon", ["Le persil", "La ciboulette", "Le thym"]),
    (2, "Quel fromage est indispensable aux pâtes carbonara traditionnelles ?", "Le pecorino romano", ["La mozzarella", "Le gruyère", "La ricotta"]),
    (2, "Quelle viande utilise la carbonara traditionnelle ?", "Le guanciale (joue de porc)", ["Les lardons fumés", "Le jambon cuit", "Le poulet"]),
    (2, "Quels sont les trois ingrédients de la pizza margherita ?", "Tomate, mozzarella, basilic", ["Tomate, jambon, champignons", "Crème, lardons, oignons", "Tomate, anchois, olives"]),
    (2, "Quelles couleurs de la pizza margherita rappellent le drapeau italien ?", "Rouge, blanc, vert", ["Rouge, jaune, vert", "Bleu, blanc, rouge", "Vert, blanc, orange"]),
    (2, "Quel fromage met-on dans une fondue moitié-moitié ?", "Gruyère et vacherin fribourgeois", ["Gruyère et emmental", "Comté et beaufort", "Raclette et tomme"]),
    (2, "Quel vin blanc ajoute-t-on traditionnellement à la fondue ?", "Un vin blanc sec (chasselas)", ["Un vin rouge", "Un vin doux", "Du champagne"]),
    (2, "Quel alcool ajoute-t-on souvent à la fondue ?", "Le kirsch", ["Le rhum", "Le cognac", "La vodka"]),
    (2, "Comment s'appelle la croûte de fromage grillé au fond du caquelon ?", "La religieuse", ["La croûte", "La sorcière", "La grillade"]),
    (2, "Qu'accompagne-t-on traditionnellement à la raclette ?", "Des pommes de terre en robe des champs", ["Du riz", "Des pâtes", "Du pain uniquement"]),
    (2, "Avec quoi fait-on les röstis ?", "Des pommes de terre râpées", ["Du riz", "Du fromage râpé", "De la semoule"]),
    (2, "Qui a inventé le birchermüesli ?", "Le médecin Maximilian Bircher-Benner", ["Le chocolatier Lindt", "Le cuisinier Escoffier", "Henri Nestlé"]),
    (2, "Quel Suisse a fondé une célèbre entreprise de farine lactée à Vevey ?", "Henri Nestlé", ["Philippe Suchard", "Rodolphe Lindt", "Daniel Peter"]),
    (2, "Quelle marque de chocolat suisse a la forme triangulaire du Cervin ?", "Toblerone", ["Lindt", "Cailler", "Frey"]),
    (2, "Quelle est la plus ancienne marque de chocolat suisse encore existante (1819) ?", "Cailler", ["Lindt", "Suchard", "Toblerone"]),
    (2, "Dans quel pays le cacao est-il le plus produit ?", "La Côte d'Ivoire", ["Le Brésil", "La Suisse", "L'Équateur"]),
    (2, "Quel pays produit le plus de café ?", "Le Brésil", ["La Colombie", "Le Viêt Nam", "L'Éthiopie"]),
    (2, "De quel pays le café serait-il originaire ?", "L'Éthiopie", ["Le Brésil", "Le Yémen", "La Colombie"]),
    (2, "Quel café est un espresso allongé d'eau chaude ?", "L'americano", ["Le ristretto", "Le macchiato", "Le cappuccino"]),
    (2, "Quel café est un espresso très court ?", "Le ristretto", ["Le lungo", "L'americano", "Le latte"]),
    (2, "Quel café italien est fait d'espresso, de lait et de mousse de lait ?", "Le cappuccino", ["Le ristretto", "L'affogato", "Le lungo"]),
    (2, "Comment s'appelle un espresso versé sur une boule de glace ?", "Un affogato", ["Un frappé", "Un macchiato", "Un granité"]),
    (2, "De quelle plante est tiré le thé ?", "Le théier (Camellia sinensis)", ["Le caféier", "Le rooibos", "La verveine"]),
    (2, "Quel thé japonais se présente en poudre verte ?", "Le matcha", ["Le sencha", "Le oolong", "Le darjeeling"]),
    (2, "Quelle région indienne a donné son nom à un célèbre thé noir ?", "Darjeeling", ["Bombay", "Goa", "Kerala"]),
    (2, "Quel thé est parfumé à la bergamote ?", "L'Earl Grey", ["Le darjeeling", "Le Lapsang souchong", "Le chai"]),
    (2, "Quel fruit est le plus produit au monde ?", "La banane", ["La pomme", "L'orange", "Le raisin"]),
    (2, "Quel agrume ressemble à une grosse orange au goût amer et acidulé ?", "Le pamplemousse", ["La mandarine", "Le kumquat", "La clémentine"]),
    (2, "Quel fruit est surnommé « le roi des fruits » en Asie, connu pour son odeur forte ?", "Le durian", ["Le jacquier", "Le ramboutan", "Le litchi"]),
    (2, "Quel fruit exotique a une peau rose et une chair blanche avec des pépins noirs ?", "Le fruit du dragon (pitaya)", ["Le fruit de la passion", "Le litchi", "La goyave"]),
    (2, "Quelle variété de riz utilise-t-on pour un risotto ?", "L'arborio", ["Le basmati", "Le thaï", "Le riz gluant"]),
    (2, "Quelle variété de riz parfumé vient d'Inde et du Pakistan ?", "Le basmati", ["L'arborio", "Le carnaroli", "Le riz rond"]),
    (2, "Quelle pâte en forme de papillon ?", "Les farfalle", ["Les penne", "Les fusilli", "Les orecchiette"]),
    (2, "Quelles pâtes ont la forme de petites oreilles ?", "Les orecchiette", ["Les farfalle", "Les conchiglie", "Les rigatoni"]),
    (2, "Quelles pâtes sont en forme de tubes coupés en biais ?", "Les penne", ["Les fusilli", "Les tagliatelle", "Les farfalle"]),
    (2, "Quelles pâtes sont en forme de spirales ?", "Les fusilli", ["Les penne", "Les rigatoni", "Les linguine"]),
    (2, "Quel fromage râpé est appelé « le roi des fromages » en Italie ?", "Le parmigiano reggiano", ["Le pecorino", "Le grana padano", "Le provolone"]),
    (2, "Quel fromage a des trous appelés « yeux » ?", "L'emmental", ["Le gruyère", "Le comté", "Le parmesan"]),
    (2, "Quelle moisissure donne son goût au roquefort ?", "Le Penicillium roqueforti", ["Le Penicillium camemberti", "La levure de bière", "Le koji"]),
    (2, "Dans quelles grottes est affiné le roquefort ?", "Les caves de Combalou", ["Les grottes de Lascaux", "Les caves de Gruyère", "Les grottes de Han"]),
    (2, "Quelle partie du bœuf donne le filet ?", "Le dos (longe), à l'intérieur", ["L'épaule", "La cuisse", "Le ventre"]),
    (2, "Quelle cuisson pour un steak « bleu » ?", "À peine saisi, presque cru à l'intérieur", ["Bien cuit", "À point", "Saignant"]),
    (2, "Qu'est-ce qu'un tartare ?", "De la viande ou du poisson cru haché", ["Une sauce", "Une viande fumée", "Un plat mijoté"]),
    (2, "Quel poisson est utilisé pour le thon rouge des sushis ?", "Le thon", ["Le saumon", "La daurade", "Le maquereau"]),
    (2, "Quelle algue entoure les makis ?", "La feuille de nori", ["Le wakamé", "Le kombu", "La spiruline"]),
    (2, "Quelle pâte verte pimentée accompagne les sushis ?", "Le wasabi", ["Le gingembre mariné", "Le miso", "Le yuzu"]),
    (2, "Quel aliment fermenté coréen est à base de chou pimenté ?", "Le kimchi", ["Le miso", "Le natto", "La choucroute"]),
    (2, "Quel champignon est le plus cher du monde ?", "La truffe blanche", ["Le cèpe", "Le morille", "Le shiitake"]),
    (2, "Quel animal utilise-t-on traditionnellement pour chercher les truffes ?", "Le cochon (ou le chien)", ["La chèvre", "Le furet", "Le chat"]),
    (2, "Quel chef suisse a été élu « cuisinier du siècle » par le Gault et Millau ?", "Frédy Girardet", ["Anton Mosimann", "Philippe Rochat", "Benoît Violier"]),
    (2, "Quel chef français est surnommé « le pape de la gastronomie » ?", "Paul Bocuse", ["Alain Ducasse", "Joël Robuchon", "Cyril Lignac"]),
    (2, "Quel guide gastronomique attribue des étoiles ?", "Le guide Michelin", ["Le Gault et Millau", "Le Petit Futé", "Le Routard"]),
    (2, "Quel guide note les restaurants sur 20 avec des toques ?", "Le Gault et Millau", ["Le guide Michelin", "Le Bottin gourmand", "Le Fooding"]),
    (2, "Combien d'étoiles au maximum attribue le guide Michelin ?", "3", ["5", "4", "2"]),
    (2, "Quel pâtissier français est surnommé « le Picasso de la pâtisserie » ?", "Pierre Hermé", ["Cyril Lignac", "Christophe Michalak", "Philippe Conticini"]),
    (2, "Quel gâteau est fait de pâte à choux et de crème au pralin, en forme de roue ?", "Le paris-brest", ["L'éclair", "Le saint-honoré", "La religieuse"]),
    (2, "Quel gâteau est composé de deux choux superposés ?", "La religieuse", ["Le paris-brest", "Le saint-honoré", "La croquembouche"]),
    (2, "Quelle pièce montée de choux sert aux mariages ?", "La croquembouche", ["Le fraisier", "Le saint-honoré", "Le vacherin glacé"]),
    (2, "Quel gâteau au chocolat autrichien porte le nom d'un hôtel de Vienne ?", "La sachertorte", ["La forêt-noire", "Le strudel", "La linzertorte"]),
    (2, "Quelle galette mange-t-on à l'Épiphanie ?", "La galette des rois", ["La galette bretonne", "La couronne des rois", "Le kouglof"]),
    (2, "Qu'est-ce que la bûche de Noël ?", "Un gâteau roulé en forme de bûche", ["Un pain d'épices", "Une glace en cornet", "Une tarte aux fruits"]),
]
WRITTEN += [
    (2, "Quelle fête genevoise célèbre-t-on avec une marmite en chocolat ?", "L'Escalade", ["La Fête des Vignerons", "Le Carnaval", "La Saint-Nicolas"]),
    (2, "Que veut dire « flamber » ?", "Arroser d'alcool et l'enflammer", ["Cuire au barbecue", "Griller au chalumeau", "Faire bouillir"]),
    (2, "Quelle émission culinaire oppose des candidats sous l'œil de chefs étoilés en France ?", "Top Chef", ["Le Meilleur Pâtissier", "Cauchemar en cuisine", "Les Reines du shopping"]),
    (2, "Que met-on dans le caquelon avant la fondue pour le parfumer ?", "De l'ail frotté", ["Du thym", "Du poivre", "De la muscade"]),
    (2, "Comment s'appelle la réaction qui fait dorer et donne du goût à la viande grillée ?", "La réaction de Maillard", ["La caramélisation", "La fermentation", "L'oxydation"]),
]


def generate():
    out = []
    names = {bare(c[1]): c[1] for c in COUNTRIES}
    countries = list(dict.fromkeys(c for _, c in DISHES))
    for dish, country in DISHES:
        d = 1 if dish in FAMOUS_DISHES else 2
        label = dish[0].upper() + dish[1:]
        out.append(make("cuisine", f"De quel pays vient {dish} ?", country, pick(f"dish-{dish}", countries, country), d))
    by_c = {}
    for dish, country in DISHES:
        by_c.setdefault(country, []).append(dish)
    for country, dishes in by_c.items():
        others = [x for x, c in DISHES if c != country]
        art = de(names.get(country, country))
        for dish in dishes:
            out.append(make("cuisine", f"Lequel de ces plats est une spécialité {art} ?", dish[0].upper() + dish[1:],
                            [o[0].upper() + o[1:] for o in pick(f"dishr-{dish}", others, dish)], 1 if dish in FAMOUS_DISHES else 2))
    ccountries = list(dict.fromkeys(c for _, c in CHEESES))
    for ch, country in CHEESES:
        out.append(make("cuisine", f"De quel pays vient {ch} ?", country, pick(f"ch-{ch}", ccountries, country), 2))
    by_ch = {}
    for ch, country in CHEESES:
        by_ch.setdefault(country, []).append(ch)
    for country, chs in by_ch.items():
        others = [x for x, c in CHEESES if c != country]
        for ch in chs[:5]:
            out.append(make("cuisine", f"Lequel de ces fromages vient {de(names.get(country, country))} ?", ch[0].upper() + ch[1:],
                            [o[0].upper() + o[1:] for o in pick(f"chr-{ch}", others, ch)], 2))
    for ch, milk in CHEESE_MILK:
        out.append(make("cuisine", f"Avec quel lait est fabriqué {ch} ?", milk, pick(f"milk-{ch}", ["Vache", "Brebis", "Chèvre", "Bufflonne"], milk), 2))
    dcountries = list(dict.fromkeys(c for _, c in DRINKS))
    regions = list(dict.fromkeys(r for _, r in FR_REGIONS))
    for spec, reg in FR_REGIONS:
        out.append(make("cuisine", f"De quelle région française vient {spec} ?", reg, pick(f"frreg-{spec}", regions, reg), 2))
    for spec, reg in FR_REGIONS:
        others = [x for x, r in FR_REGIONS if r != reg]
        where = {"Lyon (Lyonnais)": "de la région lyonnaise", "Nice (Comté de Nice)": "de la région niçoise", "Nord": "du Nord", "Bordelais": "du Bordelais",
                 "Périgord": "du Périgord", "Languedoc": "du Languedoc", "Maine": "du Maine", "Pays basque": "du Pays basque"}.get(reg) or de(reg if reg[0] in "AEIOUÉ" else reg)
        out.append(make("cuisine", f"Laquelle de ces spécialités vient {where} ?", spec[0].upper() + spec[1:],
                        [o[0].upper() + o[1:] for o in pick(f"frregr-{spec}", others, spec)], 2))
    for dr, country in DRINKS:
        out.append(make("cuisine", f"De quel pays vient {dr} ?", country, pick(f"dr-{dr}", dcountries, country), 2))
    wcountries = list(dict.fromkeys(c for _, c in WINE_REGIONS))
    for reg, country in WINE_REGIONS:
        out.append(make("cuisine", f"Dans quel pays se trouve la région viticole : {reg} ?", country, pick(f"wine-{reg}", wcountries, country), 2))
    ings = list(dict.fromkeys(i for _, i in INGREDIENTS))
    for dish, ing in INGREDIENTS:
        out.append(make("cuisine", f"Quel est l'ingrédient principal de {dish} ?", ing, pick(f"ing-{dish}", ings, ing), 2))
    seen_ing = set()
    for dish, ing in INGREDIENTS:
        if ing in seen_ing:
            continue  # « Quel plat est à base de riz ? » aurait plusieurs bonnes réponses
        seen_ing.add(ing)
        others = [d for d, i in INGREDIENTS if i != ing]
        out.append(make("cuisine", f"Quel plat ou produit est à base de : {ing[0].lower() + ing[1:]} ?", dish[0].upper() + dish[1:],
                        [o[0].upper() + o[1:] for o in pick(f"ingr-{dish}", others, dish)], 2))
    for c, base in COCKTAILS:
        out.append(make("cuisine", f"Quel est l'alcool de base du cocktail « {c} » ?", base,
                        pick(f"ck-{c}", BASES + ["L'Aperol et le prosecco", "Le champagne"], base, key=lambda x: x.split(" (")[0]), 2))
    # Spécialités suisses par canton → thème Suisse
    from .gen_suisse import cde
    cantons = ["Vaud", "Valais", "Fribourg", "Genève", "Neuchâtel", "Jura", "Berne", "Grisons", "Tessin", "Zurich", "Bâle-Ville", "Zoug",
               "Argovie", "Appenzell Rhodes-Intérieures", "Saint-Gall", "Lucerne"]
    for dish, canton in SWISS_DISHES:
        out.append(make("suisse", f"De quel canton est originaire cette spécialité : {dish} ?", canton, pick(f"swd-{dish}", cantons, canton), 2))
    for ch, canton in SWISS_CHEESES:
        out.append(make("suisse", f"De quel canton vient {ch} ?", canton, pick(f"swc-{ch}", cantons, canton), 2))
    for d, q, a, w in WRITTEN:
        out.append(make("cuisine", q, a, w, d))
    return out
