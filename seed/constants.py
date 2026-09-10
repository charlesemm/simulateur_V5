"""Centralise les libellés métier plausibles utilisés par le seed CMU."""

# Les localités permettent de répartir les centres sur le territoire ivoirien.
IVORIAN_CITIES = [
    "Abidjan-Cocody", "Abidjan-Yopougon", "Abidjan-Abobo", "Abidjan-Treichville",
    "Abidjan-Port-Bouët", "Bouaké", "Yamoussoukro", "San-Pédro", "Korhogo",
    "Daloa", "Man", "Gagnoa", "Abengourou", "Bondoukou", "Divo",
]

HEALTH_CENTER_TYPES = [
    ("HG", "Hôpital général"),
    ("CHR", "Centre hospitalier régional"),
    ("CSU", "Centre de santé urbain"),
    ("CSR", "Centre de santé rural"),
    ("CLN", "Clinique médicale"),
    ("PMI", "Centre de protection maternelle et infantile"),
]

# Ces noms complètent Faker avec une représentation ivoirienne identifiable.
IVORIAN_LAST_NAMES = [
    "Kouassi", "Yao", "Koné", "Ouattara", "Traoré", "Bamba", "N'Guessan",
    "Koffi", "Aka", "Amani", "Kouamé", "Diabaté", "Fofana", "Touré", "Soro",
    "Coulibaly", "Gnahoré", "Dago", "Zadi", "Assi", "Bakayoko", "Kouadio",
    "N'Dri", "Guei", "Doumbia", "Kanga", "Aké", "Brou", "Adjoumani", "Yapi",
]

IVORIAN_FIRST_NAMES = [
    "Aïssata", "Aminata", "Aya", "Fatoumata", "Mariame", "Nafissatou",
    "Affoué", "Akissi", "Amenan", "Awa", "Mariam", "Grâce", "Kady", "Mawa",
    "Adama", "Bakary", "Brahima", "Cheick", "Daouda", "Didier", "Ibrahim",
    "Ismaël", "Jean-Marc", "Kader", "Karim", "Mamadou", "Moussa", "Oumar",
    "Serge", "Souleymane",
]

MEDICAL_SPECIALTIES = [
    ("GEN", "Médecine générale"), ("PED", "Pédiatrie"),
    ("GYN", "Gynécologie-obstétrique"), ("DEN", "Odontostomatologie"),
    ("RAD", "Radiologie et imagerie médicale"), ("CAR", "Cardiologie"),
    ("DER", "Dermatologie"), ("ORL", "Oto-rhino-laryngologie"),
    ("OPH", "Ophtalmologie"), ("CHI", "Chirurgie générale"),
    ("MIR", "Médecine interne"), ("INF", "Maladies infectieuses"),
    ("NEU", "Neurologie"), ("PNE", "Pneumologie"),
    ("GAS", "Gastro-entérologie"), ("URO", "Urologie"),
    ("END", "Endocrinologie-diabétologie"), ("RHU", "Rhumatologie"),
]

# Cent pathologies courantes, classées en dix familles de dix codes.
PATHOLOGY_LABELS = [
    "Paludisme simple", "Paludisme grave", "Fièvre typhoïde", "Dengue",
    "Infection à VIH", "Tuberculose pulmonaire", "Hépatite virale B",
    "Hépatite virale C", "Amibiase intestinale", "Schistosomiase",
    "Rhinopharyngite aiguë", "Angine aiguë", "Sinusite aiguë", "Otite moyenne",
    "Bronchite aiguë", "Pneumonie communautaire", "Asthme bronchique",
    "Bronchopneumopathie chronique", "Grippe saisonnière", "COVID-19",
    "Hypertension artérielle", "Insuffisance cardiaque", "Cardiopathie ischémique",
    "Trouble du rythme cardiaque", "Accident vasculaire cérébral",
    "Thrombose veineuse profonde", "Artériopathie périphérique", "Péricardite",
    "Cardiomyopathie", "Hypotension artérielle",
    "Diabète de type 1", "Diabète de type 2", "Hypoglycémie",
    "Dyslipidémie", "Obésité", "Goitre thyroïdien", "Hyperthyroïdie",
    "Hypothyroïdie", "Malnutrition aiguë", "Carence en vitamine D",
    "Gastro-entérite aiguë", "Reflux gastro-œsophagien", "Gastrite",
    "Ulcère gastroduodénal", "Constipation", "Diarrhée infectieuse",
    "Hémorroïdes", "Hernie inguinale", "Appendicite aiguë", "Lithiase biliaire",
    "Infection urinaire", "Pyélonéphrite", "Insuffisance rénale aiguë",
    "Maladie rénale chronique", "Lithiase urinaire", "Hypertrophie prostatique",
    "Prostatite", "Syndrome néphrotique", "Incontinence urinaire", "Vaginite",
    "Anémie ferriprive", "Drépanocytose", "Anémie palustre", "Leucopénie",
    "Thrombopénie", "Trouble de la coagulation", "Leucémie", "Lymphome",
    "Carence en folates", "Anémie mégaloblastique",
    "Dermatite atopique", "Eczéma de contact", "Urticaire", "Gale",
    "Teigne", "Impétigo", "Abcès cutané", "Acné", "Mycose cutanée", "Psoriasis",
    "Arthrose du genou", "Lombalgie commune", "Cervicalgie", "Arthrite",
    "Goutte", "Fracture fermée", "Entorse de cheville", "Tendinite",
    "Sciatique", "Ostéomyélite",
    "Conjonctivite", "Cataracte", "Glaucome", "Carie dentaire",
    "Gingivite", "Parodontite", "Migraine", "Épilepsie",
    "Trouble anxieux", "Dépression",
]

# Chaque entrée produit quatre présentations cohérentes, soit 200 médicaments.
MEDICATION_SEEDS = [
    ("Paracétamol", "PAR", ["500 mg comprimé", "1 g comprimé", "120 mg/5 ml sirop", "100 mg suppositoire"], 500),
    ("Ibuprofène", "IBU", ["200 mg comprimé", "400 mg comprimé", "100 mg/5 ml suspension", "gel 5 %"], 800),
    ("Diclofénac", "DCF", ["50 mg comprimé", "75 mg injectable", "100 mg suppositoire", "gel 1 %"], 900),
    ("Tramadol", "TRA", ["50 mg gélule", "100 mg comprimé LP", "50 mg/ml injectable", "100 mg/2 ml injectable"], 1200),
    ("Amoxicilline", "AMX", ["500 mg gélule", "1 g comprimé", "250 mg/5 ml suspension", "500 mg injectable"], 1500),
    ("Amoxicilline-acide clavulanique", "AMC", ["500/62,5 mg comprimé", "1 g/125 mg comprimé", "100/12,5 mg/ml suspension", "1 g/200 mg injectable"], 2400),
    ("Azithromycine", "AZI", ["250 mg gélule", "500 mg comprimé", "200 mg/5 ml suspension", "500 mg injectable"], 1800),
    ("Ciprofloxacine", "CIP", ["250 mg comprimé", "500 mg comprimé", "200 mg/100 ml perfusion", "collyre 0,3 %"], 1400),
    ("Ceftriaxone", "CTX", ["250 mg injectable", "500 mg injectable", "1 g injectable", "2 g injectable"], 1800),
    ("Cotrimoxazole", "CTX2", ["480 mg comprimé", "960 mg comprimé", "240 mg/5 ml suspension", "480 mg injectable"], 700),
    ("Métronidazole", "MTZ", ["250 mg comprimé", "500 mg comprimé", "125 mg/5 ml suspension", "500 mg/100 ml perfusion"], 600),
    ("Artéméther-luméfantrine", "ALU", ["20/120 mg boîte 6", "20/120 mg boîte 12", "20/120 mg boîte 18", "20/120 mg boîte 24"], 1200),
    ("Artésunate", "ART", ["50 mg comprimé", "100 mg comprimé", "60 mg injectable", "120 mg injectable"], 1600),
    ("Quinine", "QUI", ["300 mg comprimé", "500 mg comprimé", "250 mg/ml injectable", "600 mg/2 ml injectable"], 1100),
    ("Albendazole", "ALB", ["200 mg comprimé", "400 mg comprimé", "200 mg/5 ml suspension", "400 mg/10 ml suspension"], 500),
    ("Oméprazole", "OME", ["10 mg gélule", "20 mg gélule", "40 mg gélule", "40 mg injectable"], 900),
    ("Pantoprazole", "PAN", ["20 mg comprimé", "40 mg comprimé", "40 mg injectable", "80 mg injectable"], 1100),
    ("Métoclopramide", "MCP", ["10 mg comprimé", "1 mg/ml solution", "10 mg/2 ml injectable", "10 mg suppositoire"], 500),
    ("Lopéramide", "LOP", ["2 mg gélule", "2 mg comprimé", "1 mg/5 ml solution", "2 mg lyoc"], 450),
    ("Sels de réhydratation orale", "SRO", ["sachet 200 ml", "sachet 500 ml", "sachet 1 litre", "solution 500 ml"], 300),
    ("Amlodipine", "AML", ["2,5 mg comprimé", "5 mg comprimé", "10 mg comprimé", "5 mg comprimé sécable"], 800),
    ("Captopril", "CAP", ["12,5 mg comprimé", "25 mg comprimé", "50 mg comprimé", "100 mg comprimé"], 600),
    ("Losartan", "LOS", ["25 mg comprimé", "50 mg comprimé", "100 mg comprimé", "50/12,5 mg comprimé"], 1000),
    ("Hydrochlorothiazide", "HCT", ["12,5 mg comprimé", "25 mg comprimé", "50 mg comprimé", "25 mg comprimé sécable"], 500),
    ("Furosémide", "FUR", ["20 mg comprimé", "40 mg comprimé", "20 mg/2 ml injectable", "250 mg/25 ml injectable"], 700),
    ("Aténolol", "ATE", ["25 mg comprimé", "50 mg comprimé", "100 mg comprimé", "50 mg comprimé sécable"], 700),
    ("Acide acétylsalicylique", "AAS", ["75 mg comprimé", "100 mg comprimé", "300 mg comprimé", "500 mg comprimé"], 450),
    ("Simvastatine", "SIM", ["10 mg comprimé", "20 mg comprimé", "40 mg comprimé", "80 mg comprimé"], 900),
    ("Metformine", "MET", ["500 mg comprimé", "850 mg comprimé", "1 g comprimé", "500 mg comprimé LP"], 700),
    ("Gliclazide", "GLI", ["30 mg comprimé LP", "60 mg comprimé LP", "80 mg comprimé", "120 mg comprimé LP"], 950),
    ("Insuline humaine rapide", "IHR", ["flacon 100 UI/ml", "cartouche 3 ml", "stylo 3 ml", "flacon 40 UI/ml"], 3500),
    ("Insuline NPH", "INP", ["flacon 100 UI/ml", "cartouche 3 ml", "stylo 3 ml", "flacon 40 UI/ml"], 3800),
    ("Salbutamol", "SAL", ["aérosol 100 µg", "2 mg comprimé", "2 mg/5 ml sirop", "5 mg/ml nébulisation"], 1200),
    ("Béclométasone", "BEC", ["aérosol 50 µg", "aérosol 100 µg", "aérosol 250 µg", "spray nasal 50 µg"], 1800),
    ("Prednisone", "PRE", ["5 mg comprimé", "20 mg comprimé", "50 mg comprimé", "5 mg/ml solution"], 650),
    ("Cétirizine", "CET", ["5 mg comprimé", "10 mg comprimé", "1 mg/ml solution", "10 mg/ml gouttes"], 600),
    ("Chlorphénamine", "CHL", ["2 mg comprimé", "4 mg comprimé", "2 mg/5 ml sirop", "10 mg/ml injectable"], 500),
    ("Fer-acide folique", "FAF", ["comprimé adulte", "comprimé grossesse", "sirop 100 ml", "solution buvable 10 ml"], 500),
    ("Acide folique", "FOL", ["1 mg comprimé", "5 mg comprimé", "10 mg comprimé", "5 mg/ml solution"], 400),
    ("Vitamine C", "VIC", ["100 mg comprimé", "500 mg comprimé", "1 g effervescent", "100 mg/ml injectable"], 450),
    ("Chlorure de sodium", "NACL", ["0,9 % poche 100 ml", "0,9 % poche 500 ml", "0,9 % poche 1 l", "10 % ampoule 10 ml"], 700),
    ("Glucose", "GLU", ["5 % poche 500 ml", "10 % poche 500 ml", "30 % ampoule 10 ml", "50 % ampoule 50 ml"], 800),
    ("Ringer lactate", "RIN", ["poche 250 ml", "poche 500 ml", "poche 1 l", "flacon 500 ml"], 900),
    ("Diazépam", "DIA", ["5 mg comprimé", "10 mg comprimé", "10 mg/2 ml injectable", "5 mg rectal"], 750),
    ("Carbamazépine", "CBZ", ["100 mg comprimé", "200 mg comprimé", "400 mg comprimé LP", "100 mg/5 ml suspension"], 1000),
    ("Acide valproïque", "VAL", ["200 mg comprimé", "500 mg comprimé", "200 mg/ml solution", "400 mg injectable"], 1400),
    ("Fluconazole", "FLU", ["50 mg gélule", "150 mg gélule", "200 mg comprimé", "200 mg/100 ml perfusion"], 1100),
    ("Clotrimazole", "CLO", ["crème 1 %", "solution 1 %", "ovule 100 mg", "ovule 500 mg"], 700),
    ("Povidone iodée", "PVI", ["solution 10 % 50 ml", "solution 10 % 125 ml", "solution moussante 125 ml", "pommade 10 %"], 600),
    ("Lidocaïne", "LID", ["gel 2 %", "spray 10 %", "injectable 1 %", "injectable 2 %"], 800),
]

INVOICE_TYPES = [
    ("AMB", "Soins ambulatoires"), ("DEN", "Soins dentaires"),
    ("BIO", "Biologie et imagerie"), ("HOS", "Hospitalisation"),
    ("PHA", "Pharmacie"),
]

MEDICAL_ACTS = [
    ("CONS-GEN", "Consultation généraliste", "consultation", "AMB", 5000),
    ("CONS-SPE", "Consultation spécialiste", "consultation", "AMB", 10000),
    ("DENT-DET", "Détartrage dentaire", "dentaire", "DEN", 15000),
    ("DENT-EXT", "Extraction dentaire", "dentaire", "DEN", 20000),
    ("DENT-CAR", "Traitement d'une carie", "dentaire", "DEN", 18000),
    ("BIO-NFS", "Numération formule sanguine", "biologie", "BIO", 5000),
    ("BIO-GLY", "Glycémie", "biologie", "BIO", 2500),
    ("BIO-CRE", "Créatininémie", "biologie", "BIO", 3500),
    ("BIO-URE", "Urémie", "biologie", "BIO", 3500),
    ("BIO-TRA", "Transaminases", "biologie", "BIO", 6000),
    ("BIO-CRP", "Protéine C-réactive", "biologie", "BIO", 6000),
    ("BIO-GEU", "Goutte épaisse paludisme", "biologie", "BIO", 3000),
    ("BIO-URI", "Examen cytobactériologique des urines", "biologie", "BIO", 7000),
    ("BIO-SEL", "Sérologie VIH", "biologie", "BIO", 4000),
    ("BIO-HBS", "Antigène HBs", "biologie", "BIO", 7000),
    ("BIO-LIP", "Bilan lipidique", "biologie", "BIO", 9000),
    ("BIO-HBA", "Hémoglobine glyquée", "biologie", "BIO", 9000),
    ("BIO-GRO", "Groupage sanguin et rhésus", "biologie", "BIO", 5000),
    ("IMG-RAD", "Radiographie standard", "imagerie", "BIO", 15000),
    ("IMG-ECH", "Échographie", "imagerie", "BIO", 25000),
    ("IMG-MAM", "Mammographie", "imagerie", "BIO", 30000),
    ("IMG-SCA", "Scanner", "imagerie", "BIO", 80000),
    ("IMG-IRM", "Imagerie par résonance magnétique", "imagerie", "BIO", 150000),
    ("HOS-MED", "Hospitalisation en médecine générale", "hospitalisation", "HOS", 25000),
    ("HOS-CHI", "Hospitalisation en chirurgie", "hospitalisation", "HOS", 40000),
    ("HOS-MAT", "Hospitalisation en maternité", "hospitalisation", "HOS", 30000),
    ("HOS-PED", "Hospitalisation en pédiatrie", "hospitalisation", "HOS", 25000),
    ("HOS-REA", "Hospitalisation en réanimation", "hospitalisation", "HOS", 100000),
    ("URG-ACC", "Accueil et prise en charge aux urgences", "urgence", "AMB,HOS", 15000),
    ("SOI-PAN", "Pansement simple", "soin", "AMB", 3000),
]


# --------------------------------------------------------------------------
# Référentiels provisoires -- à remplacer par les valeurs réelles du système
# CNAM dès qu'elles seront disponibles. Seuls les codes sont provisoires :
# la structure, elle, est celle des tables d'origine.
# --------------------------------------------------------------------------

# TYPE_IDENTIFIANT_CODE est un VARCHAR2(6) : aucun code ne peut dépasser
# six caractères.
TYPES_IDENTIFIANTS = [
    ("NNI", "Numéro national d'identification"),
    ("CNI", "Carte nationale d'identité"),
    ("RECEP", "Récépissé d'enrôlement"),
    ("CMU", "Numéro d'assuré CMU"),
    ("PASSPT", "Passeport"),
    ("ATTEST", "Attestation d'identité"),
]

# Le troisième champ porte le régime auquel la profession donne droit :
# RAM pour l'assistance médicale (100 %), RGB pour le régime général (70 %).
PROFESSIONS = [
    ("SALPR", "Salarié du secteur privé", "RGB"),
    ("SALPU", "Salarié du secteur public", "RGB"),
    ("FONCT", "Fonctionnaire", "RGB"),
    ("RETRA", "Retraité", "RGB"),
    ("INDEP", "Travailleur indépendant", "RGB"),
    ("COMMR", "Commerçant", "RGB"),
    ("ARTIS", "Artisan", "RGB"),
    ("AGRIC", "Agriculteur", "RGB"),
    ("PECHE", "Pêcheur", "RGB"),
    ("TRANS", "Transporteur", "RGB"),
    ("ENSEI", "Enseignant", "RGB"),
    ("SANTE", "Personnel de santé", "RGB"),
    ("ETUDI", "Étudiant", "RAM"),
    ("ELEVE", "Élève", "RAM"),
    ("ENFAN", "Enfant à charge", "RAM"),
    ("MENAG", "Personne au foyer", "RAM"),
    ("APPRE", "Apprenti", "RAM"),
    ("SANSE", "Sans emploi", "RAM"),
    ("INDIG", "Personne indigente", "RAM"),
    ("AUTRE", "Autre situation", "RAM"),
]

# Le code numérique 384 est celui, réel, de la Côte d'Ivoire (norme ISO
# 3166-1) -- sans lien avec le préfixe du numéro de sécurité sociale simulé
# (394, seed/runner.py:numero_securite_sociale), qui lui est arbitraire.
# (code, continent, numérique, dénomination, gentilé, indicatif, devise, lat, lon)
COUNTRIES = [
    ("CIV", "AF", 384, "Côte d'Ivoire", "Ivoirienne", 225, "XOF", 7.54, -5.55),
    ("BFA", "AF", 854, "Burkina Faso", "Burkinabè", 226, "XOF", 12.24, -1.56),
    ("MLI", "AF", 466, "Mali", "Malienne", 223, "XOF", 17.57, -3.99),
    ("GIN", "AF", 324, "Guinée", "Guinéenne", 224, "GNF", 9.95, -9.70),
    ("GHA", "AF", 288, "Ghana", "Ghanéenne", 233, "GHS", 7.95, -1.02),
    ("LBR", "AF", 430, "Liberia", "Libérienne", 231, "LRD", 6.43, -9.43),
    ("SEN", "AF", 686, "Sénégal", "Sénégalaise", 221, "XOF", 14.50, -14.45),
    ("FRA", "EU", 250, "France", "Française", 33, "EUR", 46.23, 2.21),
]

# Les quatorze districts de Côte d'Ivoire, avec leurs coordonnées
# approximatives : ils serviront de niveau « région ».
IVORIAN_DISTRICTS = [
    ("Abidjan", 5.35, -4.02),
    ("Yamoussoukro", 6.82, -5.28),
    ("Bas-Sassandra", 5.20, -6.30),
    ("Comoé", 5.85, -3.20),
    ("Denguélé", 9.75, -7.55),
    ("Gôh-Djiboua", 6.15, -5.95),
    ("Lacs", 6.90, -4.30),
    ("Lagunes", 5.85, -4.55),
    ("Montagnes", 7.40, -7.55),
    ("Sassandra-Marahoué", 6.90, -6.45),
    ("Savanes", 9.45, -5.63),
    ("Vallée du Bandama", 7.70, -5.03),
    ("Woroba", 8.45, -6.60),
    ("Zanzan", 8.05, -3.20),
]
