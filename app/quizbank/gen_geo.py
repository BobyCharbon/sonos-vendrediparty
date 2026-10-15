"""Géographie : pays (capitales, drapeaux, monnaies, continents, population, superficie), grandes villes,
États américains, provinces canadiennes, départements français."""

import random

from . import make, pick
from .fr import bare, de, flag

EU, AS, AF, AM, OC = "Europe", "Asie", "Afrique", "Amérique", "Océanie"

# (code ISO, nom avec article, capitale, continent, monnaie, population en millions, superficie en milliers de km²)
# None : donnée ambiguë (capitale contestée ou multiple, pays à cheval sur deux continents…) → pas de question dessus.
COUNTRIES = [
    # Europe
    ("FR", "la France", "Paris", EU, "euro", 68, 552),
    ("DE", "l'Allemagne", "Berlin", EU, "euro", 84, 357),
    ("IT", "l'Italie", "Rome", EU, "euro", 59, 301),
    ("ES", "l'Espagne", "Madrid", EU, "euro", 48, 506),
    ("PT", "le Portugal", "Lisbonne", EU, "euro", 10.4, 92),
    ("GB", "le Royaume-Uni", "Londres", EU, "livre sterling", 68, 243),
    ("IE", "l'Irlande", "Dublin", EU, "euro", 5.2, 70),
    ("BE", "la Belgique", "Bruxelles", EU, "euro", 11.8, 30.7),
    ("NL", "les Pays-Bas", "Amsterdam", EU, "euro", 17.9, 41.5),
    ("LU", "le Luxembourg", "Luxembourg", EU, "euro", 0.66, 2.6),
    ("CH", "la Suisse", "Berne", EU, "franc suisse", 8.8, 41.3),
    ("AT", "l'Autriche", "Vienne", EU, "euro", 9.1, 83.9),
    ("LI", "le Liechtenstein", "Vaduz", EU, "franc suisse", 0.04, 0.16),
    ("MC", "Monaco", "Monaco", EU, "euro", 0.039, 0.002),
    ("AD", "Andorre", "Andorre-la-Vieille", EU, "euro", 0.08, 0.47),
    ("SM", "Saint-Marin", "Saint-Marin", EU, "euro", 0.034, 0.061),
    ("MT", "Malte", "La Valette", EU, "euro", 0.53, 0.316),
    ("DK", "le Danemark", "Copenhague", EU, "couronne danoise", 5.9, 43),
    ("NO", "la Norvège", "Oslo", EU, "couronne norvégienne", 5.5, 385),
    ("SE", "la Suède", "Stockholm", EU, "couronne suédoise", 10.5, 450),
    ("FI", "la Finlande", "Helsinki", EU, "euro", 5.6, 338),
    ("IS", "l'Islande", "Reykjavik", EU, "couronne islandaise", 0.39, 103),
    ("EE", "l'Estonie", "Tallinn", EU, "euro", 1.37, 45),
    ("LV", "la Lettonie", "Riga", EU, "euro", 1.88, 64.6),
    ("LT", "la Lituanie", "Vilnius", EU, "euro", 2.86, 65.3),
    ("PL", "la Pologne", "Varsovie", EU, "złoty", 37.7, 313),
    ("CZ", "la Tchéquie", "Prague", EU, "couronne tchèque", 10.9, 78.9),
    ("SK", "la Slovaquie", "Bratislava", EU, "euro", 5.4, 49),
    ("HU", "la Hongrie", "Budapest", EU, "forint", 9.6, 93),
    ("SI", "la Slovénie", "Ljubljana", EU, "euro", 2.1, 20.3),
    ("HR", "la Croatie", "Zagreb", EU, "euro", 3.85, 56.6),
    ("BA", "la Bosnie-Herzégovine", "Sarajevo", EU, "mark convertible", 3.2, 51.2),
    ("RS", "la Serbie", "Belgrade", EU, "dinar serbe", 6.6, 77.5),
    ("ME", "le Monténégro", "Podgorica", EU, "euro", 0.62, 13.8),
    ("MK", "la Macédoine du Nord", "Skopje", EU, "denar", 1.8, 25.7),
    ("AL", "l'Albanie", "Tirana", EU, "lek", 2.8, 28.7),
    ("GR", "la Grèce", "Athènes", EU, "euro", 10.4, 132),
    ("BG", "la Bulgarie", "Sofia", EU, "lev", 6.4, 111),
    ("RO", "la Roumanie", "Bucarest", EU, "leu roumain", 19, 238),
    ("MD", "la Moldavie", "Chisinau", EU, "leu moldave", 2.5, 33.8),
    ("UA", "l'Ukraine", "Kiev", EU, "hryvnia", 37, 604),
    ("BY", "la Biélorussie", "Minsk", EU, "rouble biélorusse", 9.2, 208),
    ("RU", "la Russie", "Moscou", None, "rouble", 144, 17098),
    ("CY", "Chypre", "Nicosie", None, "euro", 1.26, 9.25),
    ("TR", "la Turquie", "Ankara", None, "livre turque", 85, 784),
    ("GE", "la Géorgie", "Tbilissi", None, "lari", 3.7, 69.7),
    ("AM", "l'Arménie", "Erevan", None, "dram", 2.8, 29.7),
    ("AZ", "l'Azerbaïdjan", "Bakou", None, "manat azerbaïdjanais", 10.1, 86.6),
    # Asie
    ("CN", "la Chine", "Pékin", AS, "yuan", 1410, 9597),
    ("JP", "le Japon", "Tokyo", AS, "yen", 124, 378),
    ("KR", "la Corée du Sud", "Séoul", AS, "won sud-coréen", 51.7, 100),
    ("KP", "la Corée du Nord", "Pyongyang", AS, "won nord-coréen", 26, 120.5),
    ("MN", "la Mongolie", "Oulan-Bator", AS, "tugrik", 3.4, 1564),
    ("IN", "l'Inde", "New Delhi", AS, "roupie indienne", 1430, 3287),
    ("PK", "le Pakistan", "Islamabad", AS, "roupie pakistanaise", 240, 796),
    ("BD", "le Bangladesh", "Dacca", AS, "taka", 172, 148),
    ("LK", "le Sri Lanka", None, AS, "roupie srilankaise", 22, 65.6),
    ("NP", "le Népal", "Katmandou", AS, "roupie népalaise", 30, 147),
    ("BT", "le Bhoutan", "Thimphou", AS, "ngultrum", 0.78, 38.4),
    ("MV", "les Maldives", "Malé", AS, "rufiyaa", 0.52, 0.3),
    ("AF", "l'Afghanistan", "Kaboul", AS, "afghani", 41, 652),
    ("IR", "l'Iran", "Téhéran", AS, "rial iranien", 89, 1648),
    ("IQ", "l'Irak", "Bagdad", AS, "dinar irakien", 45, 438),
    ("SY", "la Syrie", "Damas", AS, "livre syrienne", 23, 185),
    ("LB", "le Liban", "Beyrouth", AS, "livre libanaise", 5.4, 10.4),
    ("IL", "Israël", None, AS, "shekel", 9.8, 22),
    ("JO", "la Jordanie", "Amman", AS, "dinar jordanien", 11.3, 89),
    ("SA", "l'Arabie saoudite", "Riyad", AS, "riyal saoudien", 36, 2150),
    ("YE", "le Yémen", "Sanaa", AS, "rial yéménite", 34, 528),
    ("OM", "Oman", "Mascate", AS, "rial omanais", 4.6, 310),
    ("AE", "les Émirats arabes unis", "Abou Dabi", AS, "dirham des Émirats", 9.5, 83.6),
    ("QA", "le Qatar", "Doha", AS, "riyal qatari", 2.7, 11.6),
    ("BH", "Bahreïn", "Manama", AS, "dinar bahreïni", 1.5, 0.78),
    ("KW", "le Koweït", "Koweït", AS, "dinar koweïtien", 4.3, 17.8),
    ("KZ", "le Kazakhstan", "Astana", None, "tenge", 19.6, 2725),
    ("UZ", "l'Ouzbékistan", "Tachkent", AS, "sum", 36, 449),
    ("TM", "le Turkménistan", "Achgabat", AS, "manat turkmène", 6.5, 488),
    ("KG", "le Kirghizistan", "Bichkek", AS, "som", 7, 200),
    ("TJ", "le Tadjikistan", "Douchanbé", AS, "somoni", 10, 143),
    ("TH", "la Thaïlande", "Bangkok", AS, "baht", 70, 513),
    ("VN", "le Viêt Nam", "Hanoï", AS, "dong", 99, 331),
    ("LA", "le Laos", "Vientiane", AS, "kip", 7.6, 237),
    ("KH", "le Cambodge", "Phnom Penh", AS, "riel", 17, 181),
    ("MM", "la Birmanie", "Naypyidaw", AS, "kyat", 54, 677),
    ("MY", "la Malaisie", "Kuala Lumpur", AS, "ringgit", 34, 330),
    ("SG", "Singapour", "Singapour", AS, "dollar de Singapour", 5.9, 0.73),
    ("ID", "l'Indonésie", "Jakarta", AS, "roupie indonésienne", 277, 1905),
    ("PH", "les Philippines", "Manille", AS, "peso philippin", 117, 300),
    ("BN", "Brunei", "Bandar Seri Begawan", AS, "dollar de Brunei", 0.45, 5.8),
    ("TL", "le Timor oriental", "Dili", AS, None, 1.3, 14.9),
    ("TW", "Taïwan", "Taipei", AS, "nouveau dollar de Taïwan", 23.4, 36),
    # Afrique
    ("MA", "le Maroc", "Rabat", AF, "dirham marocain", 37, 447),
    ("DZ", "l'Algérie", "Alger", AF, "dinar algérien", 45, 2382),
    ("TN", "la Tunisie", "Tunis", AF, "dinar tunisien", 12.4, 163.6),
    ("LY", "la Libye", "Tripoli", AF, "dinar libyen", 6.9, 1760),
    ("EG", "l'Égypte", "Le Caire", AF, "livre égyptienne", 112, 1002),
    ("SD", "le Soudan", "Khartoum", AF, "livre soudanaise", 48, 1886),
    ("SS", "le Soudan du Sud", "Djouba", AF, "livre sud-soudanaise", 11, 644),
    ("ET", "l'Éthiopie", "Addis-Abeba", AF, "birr", 126, 1104),
    ("ER", "l'Érythrée", "Asmara", AF, "nakfa", 3.7, 121),
    ("DJ", "Djibouti", "Djibouti", AF, "franc de Djibouti", 1.1, 23.2),
    ("SO", "la Somalie", "Mogadiscio", AF, "shilling somalien", 18, 638),
    ("KE", "le Kenya", "Nairobi", AF, "shilling kényan", 55, 580),
    ("UG", "l'Ouganda", "Kampala", AF, "shilling ougandais", 48, 241.5),
    ("TZ", "la Tanzanie", "Dodoma", AF, "shilling tanzanien", 65, 945),
    ("RW", "le Rwanda", "Kigali", AF, "franc rwandais", 14, 26.3),
    ("BI", "le Burundi", "Gitega", AF, "franc burundais", 13, 27.8),
    ("CD", "la République démocratique du Congo", "Kinshasa", AF, "franc congolais", 102, 2345),
    ("CG", "la République du Congo", "Brazzaville", AF, "franc CFA", 6, 342),
    ("GA", "le Gabon", "Libreville", AF, "franc CFA", 2.4, 268),
    ("GQ", "la Guinée équatoriale", "Malabo", AF, "franc CFA", 1.7, 28),
    ("CM", "le Cameroun", "Yaoundé", AF, "franc CFA", 28, 475),
    ("CF", "la Centrafrique", "Bangui", AF, "franc CFA", 5.7, 623),
    ("TD", "le Tchad", "N'Djaména", AF, "franc CFA", 18, 1284),
    ("NE", "le Niger", "Niamey", AF, "franc CFA", 27, 1267),
    ("NG", "le Nigeria", "Abuja", AF, "naira", 224, 924),
    ("BJ", "le Bénin", "Porto-Novo", AF, "franc CFA", 13.7, 115),
    ("TG", "le Togo", "Lomé", AF, "franc CFA", 9, 56.8),
    ("GH", "le Ghana", "Accra", AF, "cedi", 34, 239),
    ("CI", "la Côte d'Ivoire", "Yamoussoukro", AF, "franc CFA", 29, 322),
    ("BF", "le Burkina Faso", "Ouagadougou", AF, "franc CFA", 23, 274),
    ("ML", "le Mali", "Bamako", AF, "franc CFA", 23, 1240),
    ("SN", "le Sénégal", "Dakar", AF, "franc CFA", 18, 197),
    ("GM", "la Gambie", "Banjul", AF, "dalasi", 2.8, 11.3),
    ("GW", "la Guinée-Bissau", "Bissau", AF, "franc CFA", 2.1, 36),
    ("GN", "la Guinée", "Conakry", AF, "franc guinéen", 14, 246),
    ("SL", "la Sierra Leone", "Freetown", AF, "leone", 8.8, 72),
    ("LR", "le Liberia", "Monrovia", AF, "dollar libérien", 5.4, 111),
    ("MR", "la Mauritanie", "Nouakchott", AF, "ouguiya", 4.9, 1031),
    ("CV", "le Cap-Vert", "Praia", AF, "escudo cap-verdien", 0.6, 4),
    ("AO", "l'Angola", "Luanda", AF, "kwanza", 36, 1247),
    ("ZM", "la Zambie", "Lusaka", AF, "kwacha zambien", 20.5, 753),
    ("ZW", "le Zimbabwe", "Harare", AF, None, 16.7, 391),
    ("MW", "le Malawi", "Lilongwe", AF, "kwacha malawite", 20.9, 118),
    ("MZ", "le Mozambique", "Maputo", AF, "metical", 33.9, 802),
    ("NA", "la Namibie", "Windhoek", AF, "dollar namibien", 2.6, 825),
    ("BW", "le Botswana", "Gaborone", AF, "pula", 2.7, 582),
    ("ZA", "l'Afrique du Sud", "Pretoria", AF, "rand", 62, 1221),
    ("LS", "le Lesotho", "Maseru", AF, "loti", 2.3, 30.4),
    ("SZ", "l'Eswatini", "Mbabane", AF, "lilangeni", 1.2, 17.4),
    ("MG", "Madagascar", "Antananarivo", AF, "ariary", 30, 587),
    ("MU", "Maurice", "Port-Louis", AF, "roupie mauricienne", 1.26, 2),
    ("SC", "les Seychelles", "Victoria", AF, "roupie seychelloise", 0.1, 0.46),
    ("KM", "les Comores", "Moroni", AF, "franc comorien", 0.85, 1.86),
    ("ST", "Sao Tomé-et-Principe", "Sao Tomé", AF, "dobra", 0.23, 0.96),
    # Amérique
    ("US", "les États-Unis", "Washington", AM, "dollar américain", 335, 9834),
    ("CA", "le Canada", "Ottawa", AM, "dollar canadien", 40, 9985),
    ("MX", "le Mexique", "Mexico", AM, "peso mexicain", 129, 1964),
    ("GT", "le Guatemala", "Guatemala", AM, "quetzal", 18, 109),
    ("BZ", "le Belize", "Belmopan", AM, "dollar bélizien", 0.41, 23),
    ("HN", "le Honduras", "Tegucigalpa", AM, "lempira", 10.6, 112.5),
    ("SV", "le Salvador", "San Salvador", AM, None, 6.3, 21),
    ("NI", "le Nicaragua", "Managua", AM, "córdoba", 6.9, 130),
    ("CR", "le Costa Rica", "San José", AM, "colón", 5.2, 51.1),
    ("PA", "le Panama", "Panama", AM, "balboa", 4.4, 75.4),
    ("CU", "Cuba", "La Havane", AM, "peso cubain", 11, 110),
    ("JM", "la Jamaïque", "Kingston", AM, "dollar jamaïcain", 2.8, 11),
    ("HT", "Haïti", "Port-au-Prince", AM, "gourde", 11.7, 27.75),
    ("DO", "la République dominicaine", "Saint-Domingue", AM, "peso dominicain", 11.3, 48.7),
    ("BS", "les Bahamas", "Nassau", AM, "dollar bahaméen", 0.41, 13.9),
    ("TT", "Trinité-et-Tobago", "Port-d'Espagne", AM, "dollar de Trinité-et-Tobago", 1.5, 5.1),
    ("BB", "la Barbade", "Bridgetown", AM, "dollar barbadien", 0.28, 0.43),
    ("CO", "la Colombie", "Bogota", AM, "peso colombien", 52, 1142),
    ("VE", "le Venezuela", "Caracas", AM, "bolivar", 28, 916),
    ("EC", "l'Équateur", "Quito", AM, None, 18, 256),
    ("PE", "le Pérou", "Lima", AM, "sol", 34, 1285),
    ("BO", "la Bolivie", None, AM, "boliviano", 12.4, 1099),
    ("BR", "le Brésil", "Brasilia", AM, "réal", 216, 8516),
    ("PY", "le Paraguay", "Asuncion", AM, "guarani", 6.9, 407),
    ("UY", "l'Uruguay", "Montevideo", AM, "peso uruguayen", 3.4, 176),
    ("AR", "l'Argentine", "Buenos Aires", AM, "peso argentin", 46, 2780),
    ("CL", "le Chili", "Santiago", AM, "peso chilien", 19.6, 756),
    ("GY", "le Guyana", "Georgetown", AM, "dollar guyanien", 0.81, 215),
    ("SR", "le Suriname", "Paramaribo", AM, "dollar surinamais", 0.62, 164),
    # Océanie
    ("AU", "l'Australie", "Canberra", OC, "dollar australien", 26.6, 7692),
    ("NZ", "la Nouvelle-Zélande", "Wellington", OC, "dollar néo-zélandais", 5.2, 268),
    ("PG", "la Papouasie-Nouvelle-Guinée", "Port Moresby", OC, "kina", 10.3, 463),
    ("FJ", "les Fidji", "Suva", OC, "dollar fidjien", 0.93, 18.3),
    ("WS", "les Samoa", "Apia", OC, "tala", 0.22, 2.8),
    ("TO", "les Tonga", "Nuku'alofa", OC, "pa'anga", 0.1, 0.75),
    ("VU", "le Vanuatu", "Port-Vila", OC, "vatu", 0.33, 12.2),
    ("SB", "les Îles Salomon", "Honiara", OC, "dollar des Salomon", 0.74, 28.9),
]

EASY = set("FR DE IT ES PT GB IE BE NL CH AT GR US CA MX BR AR JP CN IN RU AU EG MA TR DK SE NO FI PL".split())


def level(c) -> int:
    iso, _, _, _, _, pop, _ = c
    if iso in EASY:
        return 1
    return 3 if pop < 3 else 2


# Grandes villes (pas les capitales) → pays
CITIES = [
    ("Barcelone", "ES"), ("Séville", "ES"), ("Valence", "ES"), ("Bilbao", "ES"), ("Malaga", "ES"), ("Saragosse", "ES"), ("Grenade", "ES"),
    ("Porto", "PT"), ("Faro", "PT"), ("Coimbra", "PT"),
    ("Milan", "IT"), ("Naples", "IT"), ("Turin", "IT"), ("Florence", "IT"), ("Venise", "IT"), ("Palerme", "IT"), ("Bologne", "IT"), ("Gênes", "IT"), ("Vérone", "IT"), ("Pise", "IT"),
    ("Munich", "DE"), ("Hambourg", "DE"), ("Francfort", "DE"), ("Cologne", "DE"), ("Stuttgart", "DE"), ("Düsseldorf", "DE"), ("Dresde", "DE"), ("Leipzig", "DE"), ("Brême", "DE"), ("Nuremberg", "DE"),
    ("Lyon", "FR"), ("Marseille", "FR"), ("Toulouse", "FR"), ("Bordeaux", "FR"), ("Lille", "FR"), ("Nice", "FR"), ("Nantes", "FR"), ("Strasbourg", "FR"), ("Montpellier", "FR"),
    ("Manchester", "GB"), ("Liverpool", "GB"), ("Birmingham", "GB"), ("Édimbourg", "GB"), ("Glasgow", "GB"), ("Cardiff", "GB"), ("Belfast", "GB"), ("Oxford", "GB"), ("Cambridge", "GB"),
    ("Cork", "IE"), ("Galway", "IE"),
    ("Anvers", "BE"), ("Gand", "BE"), ("Liège", "BE"), ("Bruges", "BE"), ("Charleroi", "BE"),
    ("Rotterdam", "NL"), ("La Haye", "NL"), ("Utrecht", "NL"), ("Eindhoven", "NL"),
    ("Zurich", "CH"), ("Genève", "CH"), ("Bâle", "CH"), ("Lausanne", "CH"),
    ("Salzbourg", "AT"), ("Innsbruck", "AT"), ("Graz", "AT"), ("Linz", "AT"),
    ("Cracovie", "PL"), ("Gdansk", "PL"), ("Wroclaw", "PL"), ("Poznan", "PL"),
    ("Brno", "CZ"), ("Göteborg", "SE"), ("Malmö", "SE"), ("Bergen", "NO"), ("Aarhus", "DK"), ("Turku", "FI"),
    ("Thessalonique", "GR"), ("Istanbul", "TR"), ("Izmir", "TR"), ("Antalya", "TR"),
    ("Saint-Pétersbourg", "RU"), ("Novossibirsk", "RU"), ("Vladivostok", "RU"), ("Odessa", "UA"), ("Lviv", "UA"),
    ("Split", "HR"), ("Dubrovnik", "HR"),
    ("New York", "US"), ("Los Angeles", "US"), ("Chicago", "US"), ("Houston", "US"), ("San Francisco", "US"), ("Miami", "US"), ("Las Vegas", "US"), ("Seattle", "US"), ("Boston", "US"), ("La Nouvelle-Orléans", "US"),
    ("Montréal", "CA"), ("Toronto", "CA"), ("Vancouver", "CA"), ("Québec", "CA"), ("Calgary", "CA"),
    ("Guadalajara", "MX"), ("Cancún", "MX"), ("Monterrey", "MX"), ("Acapulco", "MX"),
    ("Rio de Janeiro", "BR"), ("São Paulo", "BR"), ("Salvador de Bahia", "BR"), ("Manaus", "BR"), ("Recife", "BR"),
    ("Medellín", "CO"), ("Cali", "CO"), ("Carthagène des Indes", "CO"), ("Cuzco", "PE"), ("Valparaíso", "CL"), ("Córdoba", "AR"), ("Rosario", "AR"), ("Mendoza", "AR"), ("Guayaquil", "EC"),
    ("Shanghai", "CN"), ("Hong Kong", "CN"), ("Canton", "CN"), ("Shenzhen", "CN"), ("Xi'an", "CN"), ("Chengdu", "CN"),
    ("Osaka", "JP"), ("Kyoto", "JP"), ("Hiroshima", "JP"), ("Sapporo", "JP"), ("Nagoya", "JP"), ("Yokohama", "JP"),
    ("Busan", "KR"), ("Bombay", "IN"), ("Calcutta", "IN"), ("Bangalore", "IN"), ("Madras", "IN"), ("Agra", "IN"), ("Jaipur", "IN"),
    ("Karachi", "PK"), ("Lahore", "PK"), ("Hô Chi Minh-Ville", "VN"), ("Phuket", "TH"), ("Chiang Mai", "TH"), ("Yogyakarta", "ID"), ("Surabaya", "ID"),
    ("Dubaï", "AE"), ("Djeddah", "SA"), ("La Mecque", "SA"), ("Ispahan", "IR"), ("Tel Aviv", "IL"), ("Samarcande", "UZ"),
    ("Casablanca", "MA"), ("Marrakech", "MA"), ("Fès", "MA"), ("Tanger", "MA"), ("Oran", "DZ"), ("Constantine", "DZ"), ("Sfax", "TN"),
    ("Alexandrie", "EG"), ("Louxor", "EG"), ("Lagos", "NG"), ("Abidjan", "CI"), ("Le Cap", "ZA"), ("Johannesburg", "ZA"), ("Durban", "ZA"),
    ("Mombasa", "KE"), ("Zanzibar", "TZ"), ("Douala", "CM"), ("Tombouctou", "ML"), ("Saint-Louis", "SN"), ("Lubumbashi", "CD"),
    ("Sydney", "AU"), ("Melbourne", "AU"), ("Brisbane", "AU"), ("Perth", "AU"), ("Adélaïde", "AU"), ("Auckland", "NZ"), ("Christchurch", "NZ"),
]

# États américains → capitale
US_STATES = [
    ("l'Alabama", "Montgomery"), ("l'Alaska", "Juneau"), ("l'Arizona", "Phoenix"), ("l'Arkansas", "Little Rock"), ("la Californie", "Sacramento"),
    ("le Colorado", "Denver"), ("le Connecticut", "Hartford"), ("le Delaware", "Dover"), ("la Floride", "Tallahassee"), ("la Géorgie", "Atlanta"),
    ("Hawaï", "Honolulu"), ("l'Idaho", "Boise"), ("l'Illinois", "Springfield"), ("l'Indiana", "Indianapolis"), ("l'Iowa", "Des Moines"),
    ("le Kansas", "Topeka"), ("le Kentucky", "Frankfort"), ("la Louisiane", "Bâton-Rouge"), ("le Maine", "Augusta"), ("le Maryland", "Annapolis"),
    ("le Massachusetts", "Boston"), ("le Michigan", "Lansing"), ("le Minnesota", "Saint Paul"), ("le Mississippi", "Jackson"), ("le Missouri", "Jefferson City"),
    ("le Montana", "Helena"), ("le Nebraska", "Lincoln"), ("le Nevada", "Carson City"), ("le New Hampshire", "Concord"), ("le New Jersey", "Trenton"),
    ("le Nouveau-Mexique", "Santa Fe"), ("l'État de New York", "Albany"), ("la Caroline du Nord", "Raleigh"), ("le Dakota du Nord", "Bismarck"), ("l'Ohio", "Columbus"),
    ("l'Oklahoma", "Oklahoma City"), ("l'Oregon", "Salem"), ("la Pennsylvanie", "Harrisburg"), ("le Rhode Island", "Providence"), ("la Caroline du Sud", "Columbia"),
    ("le Dakota du Sud", "Pierre"), ("le Tennessee", "Nashville"), ("le Texas", "Austin"), ("l'Utah", "Salt Lake City"), ("le Vermont", "Montpelier"),
    ("la Virginie", "Richmond"), ("l'État de Washington", "Olympia"), ("la Virginie-Occidentale", "Charleston"), ("le Wisconsin", "Madison"), ("le Wyoming", "Cheyenne"),
]
EASY_STATES = {"la Californie", "le Texas", "la Floride", "l'État de New York", "le Massachusetts", "la Géorgie", "le Colorado", "Hawaï", "l'Utah", "le Tennessee"}

CA_PROVINCES = [
    ("le Québec", "Québec"), ("l'Ontario", "Toronto"), ("la Colombie-Britannique", "Victoria"), ("l'Alberta", "Edmonton"),
    ("le Manitoba", "Winnipeg"), ("la Saskatchewan", "Regina"), ("la Nouvelle-Écosse", "Halifax"), ("le Nouveau-Brunswick", "Fredericton"),
    ("l'Île-du-Prince-Édouard", "Charlottetown"), ("Terre-Neuve-et-Labrador", "Saint-Jean"), ("le Yukon", "Whitehorse"),
    ("les Territoires du Nord-Ouest", "Yellowknife"), ("le Nunavut", "Iqaluit"),
]

# Départements français métropolitains (numéro, nom, préfecture)
DEPARTEMENTS = [
    ("01", "Ain", "Bourg-en-Bresse"), ("02", "Aisne", "Laon"), ("03", "Allier", "Moulins"), ("04", "Alpes-de-Haute-Provence", "Digne-les-Bains"),
    ("05", "Hautes-Alpes", "Gap"), ("06", "Alpes-Maritimes", "Nice"), ("07", "Ardèche", "Privas"), ("08", "Ardennes", "Charleville-Mézières"),
    ("09", "Ariège", "Foix"), ("10", "Aube", "Troyes"), ("11", "Aude", "Carcassonne"), ("12", "Aveyron", "Rodez"),
    ("13", "Bouches-du-Rhône", "Marseille"), ("14", "Calvados", "Caen"), ("15", "Cantal", "Aurillac"), ("16", "Charente", "Angoulême"),
    ("17", "Charente-Maritime", "La Rochelle"), ("18", "Cher", "Bourges"), ("19", "Corrèze", "Tulle"), ("21", "Côte-d'Or", "Dijon"),
    ("22", "Côtes-d'Armor", "Saint-Brieuc"), ("23", "Creuse", "Guéret"), ("24", "Dordogne", "Périgueux"), ("25", "Doubs", "Besançon"),
    ("26", "Drôme", "Valence"), ("27", "Eure", "Évreux"), ("28", "Eure-et-Loir", "Chartres"), ("29", "Finistère", "Quimper"),
    ("30", "Gard", "Nîmes"), ("31", "Haute-Garonne", "Toulouse"), ("32", "Gers", "Auch"), ("33", "Gironde", "Bordeaux"),
    ("34", "Hérault", "Montpellier"), ("35", "Ille-et-Vilaine", "Rennes"), ("36", "Indre", "Châteauroux"), ("37", "Indre-et-Loire", "Tours"),
    ("38", "Isère", "Grenoble"), ("39", "Jura", "Lons-le-Saunier"), ("40", "Landes", "Mont-de-Marsan"), ("41", "Loir-et-Cher", "Blois"),
    ("42", "Loire", "Saint-Étienne"), ("43", "Haute-Loire", "Le Puy-en-Velay"), ("44", "Loire-Atlantique", "Nantes"), ("45", "Loiret", "Orléans"),
    ("46", "Lot", "Cahors"), ("47", "Lot-et-Garonne", "Agen"), ("48", "Lozère", "Mende"), ("49", "Maine-et-Loire", "Angers"),
    ("50", "Manche", "Saint-Lô"), ("51", "Marne", "Châlons-en-Champagne"), ("52", "Haute-Marne", "Chaumont"), ("53", "Mayenne", "Laval"),
    ("54", "Meurthe-et-Moselle", "Nancy"), ("55", "Meuse", "Bar-le-Duc"), ("56", "Morbihan", "Vannes"), ("57", "Moselle", "Metz"),
    ("58", "Nièvre", "Nevers"), ("59", "Nord", "Lille"), ("60", "Oise", "Beauvais"), ("61", "Orne", "Alençon"),
    ("62", "Pas-de-Calais", "Arras"), ("63", "Puy-de-Dôme", "Clermont-Ferrand"), ("64", "Pyrénées-Atlantiques", "Pau"), ("65", "Hautes-Pyrénées", "Tarbes"),
    ("66", "Pyrénées-Orientales", "Perpignan"), ("67", "Bas-Rhin", "Strasbourg"), ("68", "Haut-Rhin", "Colmar"), ("69", "Rhône", "Lyon"),
    ("70", "Haute-Saône", "Vesoul"), ("71", "Saône-et-Loire", "Mâcon"), ("72", "Sarthe", "Le Mans"), ("73", "Savoie", "Chambéry"),
    ("74", "Haute-Savoie", "Annecy"), ("75", "Paris", "Paris"), ("76", "Seine-Maritime", "Rouen"), ("77", "Seine-et-Marne", "Melun"),
    ("78", "Yvelines", "Versailles"), ("79", "Deux-Sèvres", "Niort"), ("80", "Somme", "Amiens"), ("81", "Tarn", "Albi"),
    ("82", "Tarn-et-Garonne", "Montauban"), ("83", "Var", "Toulon"), ("84", "Vaucluse", "Avignon"), ("85", "Vendée", "La Roche-sur-Yon"),
    ("86", "Vienne", "Poitiers"), ("87", "Haute-Vienne", "Limoges"), ("88", "Vosges", "Épinal"), ("89", "Yonne", "Auxerre"),
    ("90", "Territoire de Belfort", "Belfort"), ("91", "Essonne", "Évry-Courcouronnes"), ("92", "Hauts-de-Seine", "Nanterre"), ("93", "Seine-Saint-Denis", "Bobigny"),
    ("94", "Val-de-Marne", "Créteil"), ("95", "Val-d'Oise", "Cergy"),
]
EASY_DEPTS = {"13", "33", "69", "75", "59", "74", "06", "67", "31", "44", "35", "34", "38", "73", "64", "29"}

# Fleuves, montagnes, mers… (question, bonne réponse, pool de mauvaises réponses, difficulté)
RIVERS = [  # fleuve → mer ou océan où il se jette
    ("la Seine", "la Manche"), ("la Loire", "l'océan Atlantique"), ("le Rhône", "la mer Méditerranée"), ("le Rhin", "la mer du Nord"),
    ("le Danube", "la mer Noire"), ("le Nil", "la mer Méditerranée"), ("l'Amazone", "l'océan Atlantique"), ("le Mississippi", "le golfe du Mexique"),
    ("la Volga", "la mer Caspienne"), ("le Gange", "le golfe du Bengale"), ("l'Elbe", "la mer du Nord"), ("la Tamise", "la mer du Nord"),
    ("le Pô", "la mer Adriatique"), ("l'Èbre", "la mer Méditerranée"), ("le Tage", "l'océan Atlantique"), ("le Congo", "l'océan Atlantique"),
    ("le Zambèze", "l'océan Indien"), ("l'Indus", "la mer d'Arabie"), ("le Saint-Laurent", "l'océan Atlantique"), ("la Garonne", "l'océan Atlantique"),
]
SEAS = ["la Manche", "l'océan Atlantique", "la mer Méditerranée", "la mer du Nord", "la mer Noire", "le golfe du Mexique", "la mer Caspienne",
        "le golfe du Bengale", "la mer Adriatique", "l'océan Indien", "la mer d'Arabie", "la mer Baltique", "l'océan Pacifique", "la mer Rouge"]

RIVER_COUNTRY = [  # fleuve célèbre → pays qu'il traverse (un seul parmi les choix)
    ("Quel fleuve traverse Paris ?", "La Seine", ["La Loire", "Le Rhône", "La Garonne"], 1),
    ("Quel fleuve traverse Londres ?", "La Tamise", ["La Seine", "Le Rhin", "La Severn"], 1),
    ("Quel fleuve traverse Rome ?", "Le Tibre", ["Le Pô", "L'Arno", "L'Adige"], 2),
    ("Quel fleuve traverse Florence ?", "L'Arno", ["Le Tibre", "Le Pô", "L'Adige"], 3),
    ("Quel fleuve traverse Budapest ?", "Le Danube", ["Le Rhin", "L'Elbe", "La Vistule"], 2),
    ("Quel fleuve traverse Vienne ?", "Le Danube", ["Le Rhin", "L'Elbe", "La Moldau"], 2),
    ("Quel fleuve traverse Prague ?", "La Vltava", ["Le Danube", "L'Elbe", "L'Oder"], 3),
    ("Quel fleuve traverse Varsovie ?", "La Vistule", ["L'Oder", "Le Danube", "L'Elbe"], 3),
    ("Quel fleuve traverse Le Caire ?", "Le Nil", ["Le Niger", "Le Congo", "L'Euphrate"], 1),
    ("Quel fleuve traverse Bagdad ?", "Le Tigre", ["L'Euphrate", "Le Nil", "L'Indus"], 3),
    ("Quel fleuve traverse Lyon avec la Saône ?", "Le Rhône", ["La Loire", "La Seine", "La Garonne"], 1),
    ("Quel fleuve traverse Bordeaux ?", "La Garonne", ["La Dordogne", "La Loire", "Le Lot"], 1),
    ("Quel fleuve traverse Nantes ?", "La Loire", ["La Seine", "La Garonne", "La Vilaine"], 1),
    ("Quel fleuve traverse Lisbonne ?", "Le Tage", ["Le Douro", "L'Èbre", "Le Guadalquivir"], 2),
    ("Quel fleuve traverse Séville ?", "Le Guadalquivir", ["Le Tage", "L'Èbre", "Le Douro"], 3),
    ("Quel fleuve traverse Porto ?", "Le Douro", ["Le Tage", "Le Guadiana", "L'Èbre"], 2),
    ("Quel fleuve traverse Berlin ?", "La Spree", ["Le Rhin", "L'Elbe", "Le Main"], 3),
    ("Quel fleuve traverse Hambourg ?", "L'Elbe", ["Le Rhin", "Le Weser", "L'Oder"], 2),
    ("Quel fleuve traverse Cologne ?", "Le Rhin", ["Le Danube", "L'Elbe", "Le Main"], 2),
    ("Quel fleuve traverse Bâle ?", "Le Rhin", ["Le Rhône", "L'Aar", "La Reuss"], 1),
    ("Quel fleuve traverse Genève ?", "Le Rhône", ["Le Rhin", "L'Aar", "La Sarine"], 1),
    ("Quel fleuve traverse New York (à l'ouest de Manhattan) ?", "L'Hudson", ["Le Potomac", "Le Mississippi", "Le Saint-Laurent"], 2),
    ("Quel fleuve traverse Montréal ?", "Le Saint-Laurent", ["L'Hudson", "Le Mississippi", "Le Yukon"], 1),
    ("Quel fleuve traverse Moscou ?", "La Moskova", ["La Volga", "La Neva", "Le Don"], 2),
    ("Quel fleuve traverse Saint-Pétersbourg ?", "La Neva", ["La Moskova", "La Volga", "Le Dniepr"], 3),
    ("Quel fleuve traverse Kiev ?", "Le Dniepr", ["Le Danube", "La Volga", "Le Don"], 3),
    ("Quel fleuve traverse Shanghai ?", "Le Huangpu", ["Le Mékong", "L'Indus", "Le Gange"], 3),
    ("Quel fleuve sacré traverse Varanasi (Bénarès) ?", "Le Gange", ["L'Indus", "Le Brahmapoutre", "Le Mékong"], 2),
    ("Quel fleuve traverse Buenos Aires ?", "Le Río de la Plata", ["L'Amazone", "L'Orénoque", "Le Paraná"], 3),
    ("Quel fleuve traverse Belgrade ?", "Le Danube", ["La Vistule", "Le Rhin", "Le Dniepr"], 3),
]

MOUNTAINS = [  # sommet, massif / pays, altitude en mètres
    ("l'Everest", 8849), ("le K2", 8611), ("l'Aconcagua", 6961), ("le Denali", 6190), ("le Kilimandjaro", 5895),
    ("l'Elbrouz", 5642), ("le mont Blanc", 4806), ("le mont Rose (pointe Dufour)", 4634), ("le Cervin", 4478), ("le mont Kenya", 5199),
    ("le Mont Fuji", 3776), ("l'Etna", 3357), ("le Vésuve", 1281), ("l'Olympe", 2918), ("le Mont Cook (Aoraki)", 3724),
    ("le Kosciuszko", 2228), ("le Ben Nevis", 1345), ("l'Aneto", 3404), ("le Pic du Midi de Bigorre", 2877), ("le Puy de Dôme", 1465),
    ("le Mont Ventoux", 1910), ("la Jungfrau", 4158), ("l'Eiger", 3967), ("le Grossglockner", 3798), ("la Zugspitze", 2962),
    ("le Kangchenjunga", 8586), ("le Mauna Kea", 4207), ("le Chimborazo", 6263), ("le Mont Ararat", 5137), ("le Teide", 3715),
]

OCEANS = [
    ("Quel est le plus grand océan du monde ?", "L'océan Pacifique", ["L'océan Atlantique", "L'océan Indien", "L'océan Arctique"], 1),
    ("Quel est le plus petit océan du monde ?", "L'océan Arctique", ["L'océan Indien", "L'océan Austral", "L'océan Atlantique"], 2),
    ("Quel est le plus long fleuve d'Europe ?", "La Volga", ["Le Danube", "Le Rhin", "La Loire"], 2),
    ("Quel est le plus long fleuve de France ?", "La Loire", ["La Seine", "Le Rhône", "La Garonne"], 1),
    ("Quel est le plus grand désert chaud du monde ?", "Le Sahara", ["Le désert de Gobi", "Le Kalahari", "L'Atacama"], 1),
    ("Dans quel pays se trouve le désert d'Atacama ?", "Le Chili", ["Le Pérou", "Le Mexique", "L'Argentine"], 2),
    ("Dans quels pays s'étend le désert de Gobi ?", "La Chine et la Mongolie", ["L'Inde et le Pakistan", "L'Iran et l'Irak", "Le Kazakhstan et la Russie"], 2),
    ("Quel est le plus grand lac d'Afrique ?", "Le lac Victoria", ["Le lac Tanganyika", "Le lac Malawi", "Le lac Tchad"], 2),
    ("Quel est le lac le plus profond du monde ?", "Le lac Baïkal", ["Le lac Tanganyika", "Le lac Supérieur", "La mer Caspienne"], 2),
    ("Quelle est la plus grande île du monde ?", "Le Groenland", ["Madagascar", "Bornéo", "La Nouvelle-Guinée"], 1),
    ("Quelle mer sépare l'Europe de l'Afrique ?", "La mer Méditerranée", ["La mer Rouge", "La mer Noire", "La mer Caspienne"], 1),
    ("Quel détroit sépare l'Espagne du Maroc ?", "Le détroit de Gibraltar", ["Le détroit de Messine", "Le Bosphore", "Le détroit d'Ormuz"], 1),
    ("Quel détroit sépare l'Europe et l'Asie à Istanbul ?", "Le Bosphore", ["Les Dardanelles", "Le détroit de Gibraltar", "Le détroit de Béring"], 2),
    ("Quel détroit sépare l'Asie de l'Amérique ?", "Le détroit de Béring", ["Le détroit de Magellan", "Le Bosphore", "Le Pas de Calais"], 2),
    ("Quel canal relie la mer Méditerranée à la mer Rouge ?", "Le canal de Suez", ["Le canal de Panama", "Le canal de Corinthe", "Le canal de Kiel"], 1),
    ("Quel canal relie l'océan Atlantique à l'océan Pacifique ?", "Le canal de Panama", ["Le canal de Suez", "Le canal de Kiel", "Le canal du Midi"], 1),
    ("Quelle chaîne de montagnes sépare la France de l'Espagne ?", "Les Pyrénées", ["Les Alpes", "Le Jura", "Les Vosges"], 1),
    ("Quelle chaîne de montagnes sépare l'Europe de l'Asie ?", "L'Oural", ["Le Caucase", "Les Carpates", "L'Altaï"], 2),
    ("Dans quelle chaîne de montagnes se trouve l'Everest ?", "L'Himalaya", ["Le Karakoram", "Les Andes", "L'Hindou Kouch"], 1),
    ("Quelle est la plus longue chaîne de montagnes du monde (à l'air libre) ?", "La cordillère des Andes", ["L'Himalaya", "Les Rocheuses", "L'Oural"], 2),
    ("Quel pays compte le plus d'habitants au monde (depuis 2023) ?", "L'Inde", ["La Chine", "Les États-Unis", "L'Indonésie"], 2),
    ("Quel est le plus grand pays du monde par la superficie ?", "La Russie", ["Le Canada", "La Chine", "Les États-Unis"], 1),
    ("Quel est le plus petit pays du monde ?", "Le Vatican", ["Monaco", "Saint-Marin", "Le Liechtenstein"], 1),
    ("Quel pays a la forme d'une botte ?", "L'Italie", ["La Grèce", "Le Chili", "Le Portugal"], 1),
    ("Quel pays est surnommé « le pays du Soleil-Levant » ?", "Le Japon", ["La Chine", "La Corée du Sud", "La Thaïlande"], 1),
    ("Quel pays est surnommé « le pays des mille lacs » ?", "La Finlande", ["La Suède", "Le Canada", "La Suisse"], 2),
    ("Quel pays est surnommé « le pays du Matin calme » ?", "La Corée", ["Le Japon", "Le Viêt Nam", "La Mongolie"], 2),
    ("Quel pays est surnommé « le plat pays » ?", "La Belgique", ["Les Pays-Bas", "Le Danemark", "Le Luxembourg"], 2),
    ("Quel pays est surnommé « l'Hexagone » ?", "La France", ["La Belgique", "La Suisse", "Le Portugal"], 1),
    ("Quel pays est surnommé « la Grande Île » ?", "Madagascar", ["L'Islande", "Le Sri Lanka", "Cuba"], 2),
    ("Quel est le seul pays traversé à la fois par l'équateur et le tropique du Capricorne ?", "Le Brésil", ["L'Indonésie", "Le Kenya", "L'Équateur"], 3),
    ("Quel pays possède le plus de fuseaux horaires (avec ses territoires) ?", "La France", ["La Russie", "Les États-Unis", "Le Royaume-Uni"], 3),
    ("Combien de pays compte l'Union européenne (2024) ?", "27", ["25", "28", "30"], 2),
    ("Combien de continents compte-t-on traditionnellement en France ?", "5", ["4", "6", "7"], 2),
    ("Quelle ville est traversée par le méridien de Greenwich ?", "Londres", ["Paris", "Madrid", "Lisbonne"], 1),
    ("Quelle est la ville la plus peuplée du monde (agglomération) ?", "Tokyo", ["Shanghai", "Mexico", "New York"], 2),
    ("Quelle est la capitale la plus haute du monde (siège du gouvernement) ?", "La Paz", ["Quito", "Bogota", "Katmandou"], 3),
    ("Dans quel océan se trouvent les Maldives ?", "L'océan Indien", ["L'océan Pacifique", "L'océan Atlantique", "La mer Rouge"], 1),
    ("Dans quel océan se trouve Hawaï ?", "L'océan Pacifique", ["L'océan Indien", "L'océan Atlantique", "L'océan Arctique"], 1),
    ("Dans quelle mer se trouve la Corse ?", "La mer Méditerranée", ["La mer Adriatique", "La mer Égée", "La mer Baltique"], 1),
    ("Quel pays est formé de plus de 17 000 îles ?", "L'Indonésie", ["Les Philippines", "Le Japon", "La Grèce"], 2),
    ("Quelle est la plus grande île de la Méditerranée ?", "La Sicile", ["La Sardaigne", "La Corse", "Chypre"], 2),
    ("À quel pays appartient le Groenland ?", "Le Danemark", ["La Norvège", "Le Canada", "L'Islande"], 2),
    ("À quel pays appartiennent les Açores ?", "Le Portugal", ["L'Espagne", "La France", "Le Royaume-Uni"], 2),
    ("À quel pays appartiennent les îles Canaries ?", "L'Espagne", ["Le Portugal", "Le Maroc", "La France"], 1),
    ("À quel pays appartient l'île de la Réunion ?", "La France", ["Maurice", "Madagascar", "Le Royaume-Uni"], 1),
    ("À quel pays appartient la Sardaigne ?", "L'Italie", ["La France", "L'Espagne", "La Grèce"], 1),
    ("À quel pays appartient la Crète ?", "La Grèce", ["Chypre", "La Turquie", "L'Italie"], 1),
    ("À quel pays appartiennent les Baléares ?", "L'Espagne", ["L'Italie", "La France", "La Grèce"], 1),
    ("À quel pays appartient la Tasmanie ?", "L'Australie", ["La Nouvelle-Zélande", "Le Royaume-Uni", "L'Indonésie"], 2),
    ("Quelle est la capitale de l'Écosse ?", "Édimbourg", ["Glasgow", "Aberdeen", "Inverness"], 1),
    ("Quelle est la capitale du pays de Galles ?", "Cardiff", ["Swansea", "Bristol", "Newport"], 2),
    ("Quelle est la capitale de l'Irlande du Nord ?", "Belfast", ["Dublin", "Derry", "Cork"], 2),
    ("Quelle est la capitale de la Catalogne ?", "Barcelone", ["Gérone", "Tarragone", "Valence"], 1),
    ("Quelle est la capitale de la Bavière ?", "Munich", ["Nuremberg", "Augsbourg", "Stuttgart"], 2),
    ("Quelle est la capitale de la Sicile ?", "Palerme", ["Catane", "Messine", "Syracuse"], 2),
    ("Quelle est la capitale de la Corse ?", "Ajaccio", ["Bastia", "Corte", "Calvi"], 1),
    ("Quelle ville est la capitale de la Bretagne ?", "Rennes", ["Brest", "Nantes", "Quimper"], 1),
    ("Quelle est la plus grande ville d'Australie ?", "Sydney", ["Melbourne", "Canberra", "Brisbane"], 1),
    ("Quelle est la plus grande ville du Canada ?", "Toronto", ["Montréal", "Vancouver", "Ottawa"], 2),
    ("Quelle est la plus grande ville de Turquie ?", "Istanbul", ["Ankara", "Izmir", "Antalya"], 1),
    ("Quelle est la plus grande ville du Brésil ?", "São Paulo", ["Rio de Janeiro", "Brasilia", "Salvador"], 2),
    ("Quelle est la plus grande ville de Suisse ?", "Zurich", ["Genève", "Bâle", "Berne"], 1),
    ("Quel pays n'a pas d'accès à la mer ?", "La Suisse", ["La Belgique", "Le Portugal", "La Slovénie"], 1),
    ("Quel pays d'Amérique du Sud n'a pas d'accès à la mer ?", "Le Paraguay", ["L'Uruguay", "L'Équateur", "Le Pérou"], 2),
    ("Combien d'États compte les États-Unis ?", "50", ["48", "51", "52"], 1),
    ("Quel est le plus grand État des États-Unis ?", "L'Alaska", ["Le Texas", "La Californie", "Le Montana"], 2),
    ("Quel est l'État le plus peuplé des États-Unis ?", "La Californie", ["Le Texas", "La Floride", "L'État de New York"], 2),
    ("Combien de régions compte la France métropolitaine (depuis 2016) ?", "13", ["12", "18", "22"], 2),
    ("Quel est le point culminant de l'Afrique ?", "Le Kilimandjaro", ["Le mont Kenya", "Le Toubkal", "Le Ras Dashen"], 1),
    ("Quel est le point culminant de l'Amérique du Sud ?", "L'Aconcagua", ["Le Chimborazo", "Le Huascarán", "Le Cotopaxi"], 2),
    ("Quel est le point culminant de l'Amérique du Nord ?", "Le Denali", ["Le mont Logan", "Le mont Whitney", "Le Pic d'Orizaba"], 2),
    ("Quel est le point culminant des Alpes ?", "Le mont Blanc", ["Le mont Rose", "Le Cervin", "Le Grand Paradis"], 1),
    ("Quel est le point culminant des Pyrénées ?", "L'Aneto", ["Le Vignemale", "Le Mont Perdu", "Le Canigou"], 3),
    ("Quel volcan a détruit Pompéi en 79 ?", "Le Vésuve", ["L'Etna", "Le Stromboli", "Le Vulcano"], 1),
    ("Quel est le plus haut volcan actif d'Europe ?", "L'Etna", ["Le Vésuve", "Le Stromboli", "L'Hekla"], 2),
    ("Dans quel pays se trouve la vallée de la Mort ?", "Les États-Unis", ["Le Mexique", "Le Chili", "L'Australie"], 2),
    ("Dans quel pays se trouve le Grand Canyon ?", "Les États-Unis", ["Le Mexique", "Le Canada", "Le Pérou"], 1),
    ("Dans quel pays se trouve la baie d'Along ?", "Le Viêt Nam", ["La Thaïlande", "La Chine", "Les Philippines"], 1),
    ("Dans quel pays se trouve le Machu Picchu ?", "Le Pérou", ["La Bolivie", "Le Mexique", "L'Équateur"], 1),
    ("Dans quel pays se trouve Pétra ?", "La Jordanie", ["L'Égypte", "Israël", "Le Liban"], 2),
    ("Dans quel pays se trouve Angkor Vat ?", "Le Cambodge", ["La Thaïlande", "Le Laos", "Le Viêt Nam"], 2),
    ("Dans quel pays se trouve le Taj Mahal ?", "L'Inde", ["Le Pakistan", "L'Iran", "Le Bangladesh"], 1),
    ("Dans quel pays se trouvent les chutes Victoria ?", "La Zambie et le Zimbabwe", ["Le Kenya et la Tanzanie", "L'Afrique du Sud", "Le Botswana et la Namibie"], 2),
    ("Les chutes du Niagara sont à la frontière de quels pays ?", "Les États-Unis et le Canada", ["Le Brésil et l'Argentine", "La Zambie et le Zimbabwe", "Le Venezuela et la Colombie"], 1),
    ("Les chutes d'Iguazú sont à la frontière de quels pays ?", "L'Argentine et le Brésil", ["Le Pérou et la Bolivie", "Le Chili et l'Argentine", "La Colombie et le Venezuela"], 2),
    ("Dans quel pays se trouve l'île de Pâques ?", "Le Chili", ["Le Pérou", "La Polynésie française", "L'Équateur"], 2),
    ("Dans quel pays se trouve la Cappadoce ?", "La Turquie", ["La Grèce", "L'Arménie", "La Syrie"], 2),
    ("Dans quel pays se trouve Uluru (Ayers Rock) ?", "L'Australie", ["La Nouvelle-Zélande", "L'Afrique du Sud", "Les États-Unis"], 1),
    ("Dans quel pays se trouvent les fjords les plus célèbres ?", "La Norvège", ["La Finlande", "Le Danemark", "L'Écosse"], 1),
    ("Dans quel pays se trouve le lac Titicaca (en partie) ?", "Le Pérou", ["Le Chili", "L'Équateur", "La Colombie"], 2),
    ("Quel est le plus grand lac d'Europe occidentale ?", "Le lac Léman", ["Le lac de Constance", "Le lac de Garde", "Le lac Majeur"], 2),
    ("Quelle mer borde Venise ?", "La mer Adriatique", ["La mer Tyrrhénienne", "La mer Ionienne", "La mer Égée"], 2),
    ("Quelle mer est si salée qu'on y flotte sans effort ?", "La mer Morte", ["La mer Rouge", "La mer Noire", "La mer Caspienne"], 1),
    ("Quelle est la plus grande mer fermée (lac salé) du monde ?", "La mer Caspienne", ["La mer Morte", "La mer d'Aral", "Le lac Baïkal"], 2),
    ("Quelle ligne imaginaire divise la Terre en hémisphères Nord et Sud ?", "L'équateur", ["Le méridien de Greenwich", "Le tropique du Cancer", "La ligne de changement de date"], 1),
    ("Combien de fuseaux horaires y a-t-il sur Terre (de base) ?", "24", ["12", "36", "48"], 1),
]


def _comparisons(theme, items, label, value, q_most, q_least, n, seed, min_ratio=1.5, d_of=lambda x: 2):
    """Questions « Lequel est le plus… ? » parmi 4, avec un écart net entre le premier et le deuxième."""
    rng = random.Random(seed)
    out, tries = [], 0
    while len(out) < n and tries < n * 50:
        tries += 1
        four = rng.sample(items, 4)
        most = rng.random() < 0.6
        srt = sorted(four, key=value, reverse=most)
        a, b = value(srt[0]), value(srt[1])
        ratio = (a / b) if most else (b / a)
        if ratio < min_ratio:
            continue
        others = [label(x) for x in srt[1:]]
        q = make(theme, q_most if most else q_least, label(srt[0]), others, max(d_of(x) for x in four))
        if q:
            out.append(q)
    return out


def generate():
    out = []
    caps = [c for c in COUNTRIES if c[2]]
    cap_names = [c[2] for c in caps]
    names = [bare(c[1]) for c in COUNTRIES]
    by_iso = {c[0]: c for c in COUNTRIES}
    for c in COUNTRIES:
        iso, name, cap, cont, cur, pop, area = c
        d = level(c)
        # Choix proches : on préfère des capitales et pays du même continent (plus crédibles).
        same = [x for x in COUNTRIES if x[3] == cont and x[0] != iso] or COUNTRIES
        if cap:
            pool = [x[2] for x in same if x[2]]
            out.append(make("geo", f"Quelle est la capitale {de(name)} ?", cap, pick(f"cap-{iso}", pool if len(pool) >= 3 else cap_names, cap), d))
            out.append(make("geo", f"{cap} est la capitale de quel pays ?", bare(name), pick(f"capr-{iso}", [bare(x[1]) for x in same], bare(name)), d))
        out.append(make("geo", f"À quel pays appartient ce drapeau ? {flag(iso)}", bare(name), pick(f"flag-{iso}", [bare(x[1]) for x in same][:25], bare(name)), d))
        out.append(make("geo", f"Quel est le drapeau {de(name)} ?", flag(iso), [flag(x[0]) for x in pick(f"flagr-{iso}", same, c)], d))
        if cur:
            curs = [x[4] for x in COUNTRIES if x[4] and x[4] != cur]
            out.append(make("geo", f"Quelle est la monnaie {de(name)} ?", cur, pick(f"cur-{iso}", curs, cur), min(3, d + 1) if cur != "euro" else d))
        if cont:
            out.append(make("geo", f"Sur quel continent se trouve ce pays : {bare(name)} ?", cont, pick(f"cont-{iso}", [EU, AS, AF, AM, OC], cont), max(1, d - 1)))
    # Grandes villes → pays
    for city, iso in CITIES:
        c = by_iso[iso]
        same = [bare(x[1]) for x in COUNTRIES if x[3] == c[3] and x[0] != iso] or names
        out.append(make("geo", f"Dans quel pays se trouve la ville de {city} ?", bare(c[1]), pick(f"city-{city}", same[:25], bare(c[1])), level(c)))
    # Population et superficie
    known = [c for c in COUNTRIES if c[5] >= 1]
    out += _comparisons("geo", known, lambda c: bare(c[1]), lambda c: c[5], "Lequel de ces pays compte le plus d'habitants ?",
                        "Lequel de ces pays compte le moins d'habitants ?", 220, "pop", 1.6, level)
    out += _comparisons("geo", COUNTRIES, lambda c: bare(c[1]), lambda c: c[6], "Lequel de ces pays est le plus grand (superficie) ?",
                        "Lequel de ces pays est le plus petit (superficie) ?", 220, "area", 1.6, level)
    # Intrus de continent
    rng = random.Random("intrus")
    conts = {k: [c for c in COUNTRIES if c[3] == k] for k in (EU, AS, AF, AM, OC)}
    for i in range(160):
        k = rng.choice([EU, AS, AF, AM])
        other = rng.choice([x for x in (EU, AS, AF, AM, OC) if x != k])
        three = rng.sample(conts[k], 3)
        odd = rng.choice(conts[other])
        d = max(level(x) for x in three + [odd])
        out.append(make("geo", f"Lequel de ces pays ne se trouve pas en {k if k != AS else 'Asie'} ?" if k != AM else "Lequel de ces pays ne se trouve pas sur le continent américain ?",
                        bare(odd[1]), [bare(x[1]) for x in three], d))
    # États américains, provinces canadiennes, départements
    st_caps = [c for _, c in US_STATES]
    for st, cap in US_STATES:
        d = 2 if st in EASY_STATES else 3
        out.append(make("geo", f"Quelle est la capitale de {st} (États-Unis) ?" if not st.startswith("l'État") else f"Quelle est la capitale de {st} ?",
                        cap, pick(f"us-{st}", st_caps, cap), d))
    pv_caps = [c for _, c in CA_PROVINCES]
    for pv, cap in CA_PROVINCES:
        out.append(make("geo", f"Quelle est la capitale {de(pv)} (Canada) ?", cap, pick(f"ca-{pv}", pv_caps, cap), 2 if pv in ("le Québec", "l'Ontario") else 3))
    dnames, dprefs = [d[1] for d in DEPARTEMENTS], [d[2] for d in DEPARTEMENTS]
    for num, nm, pref in DEPARTEMENTS:
        d = 2 if num in EASY_DEPTS else 3
        out.append(make("geo", f"Quel département français porte le numéro {num} ?", nm, pick(f"dep-{num}", dnames, nm), d))
        if nm != pref:
            out.append(make("geo", f"Quelle est la préfecture du département « {nm} » ({num}) ?", pref, pick(f"pref-{num}", dprefs, pref), d))
    # Fleuves, sommets, divers
    for river, sea in RIVERS:
        out.append(make("geo", f"Dans quelle mer ou quel océan se jette {river} ?", sea[0].upper() + sea[1:],
                        [s[0].upper() + s[1:] for s in pick(f"riv-{river}", SEAS, sea)], 2))
    for q, a, w, d in RIVER_COUNTRY + OCEANS:
        out.append(make("geo", q, a, w, d))
    out += _comparisons("geo", MOUNTAINS, lambda m: m[0][0].upper() + m[0][1:], lambda m: m[1], "Lequel de ces sommets est le plus haut ?",
                        "Lequel de ces sommets est le moins haut ?", 120, "mount", 1.12)
    return out
