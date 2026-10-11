// Tout le contenu éditable du site est ici.
// Les valeurs entre crochets [ ... ] sont des PLACEHOLDERS à remplacer par les vraies infos du client.

export const LINKS = {
  // [PLACEHOLDER] Lien Calendly réel du client
  booking: 'https://calendly.com/[lien-calendly-a-fournir]',
  // [PLACEHOLDER] Numéro WhatsApp au format international sans + ni espaces (ex. 33612345678)
  whatsapp: 'https://wa.me/33000000000',
  whatsappLabel: '[06 XX XX XX XX]',
  // [PLACEHOLDER] Email de contact
  email: '[contact@oblique-coaching.fr]',
  instagram: 'https://www.instagram.com/oblique.coaching/',
  linkedin: 'https://www.linkedin.com/in/jahengarcaut',
}

export const CTA = {
  primary: 'Réserver ma séance découverte',
  secondary: 'Découvrir la méthode',
}

export const BRAND = {
  name: 'Oblique Coaching',
  coach: 'Jahen Garçaut',
  slogan: 'Une méthode. Un objectif. Des résultats.',
}

export const HERO = {
  kicker: 'Coach sportif & nutrition · Bourges',
  // Deux lignes de titre. "CONTRÔLE." est mis en rouge.
  lines: ['REPRENEZ', 'LE CONTRÔLE.'],
  sub: '(Re)prenez le sport pour (re)prendre soin de vous : coaching sportif et nutrition sur mesure, à domicile, en entreprise ou en ligne. Bourges & alentours.',
  // Preuves sociales placées tôt (issues de la bio Instagram du client)
  proofs: ['Premier bilan offert', '+30 personnes accompagnées', 'À domicile · En ligne'],
}

// Section problème : le visiteur doit se reconnaître avant qu'on lui présente la méthode
export const PROBLEM = {
  title: ['Le plus dur,', 'c’est de s’y remettre.'],
  pains: [
    'Vous avez arrêté le sport depuis des mois, parfois des années, et vous ne savez plus par où recommencer.',
    'Vous avez déjà essayé seul : un abonnement, de bonnes résolutions, puis la motivation qui s’essouffle au bout de quelques semaines.',
    'Votre agenda est plein. Chaque séance doit compter, sans risque de vous blesser.',
  ],
  promise:
    'Pour reprendre durablement, il vous faut trois choses : un cadre, un plan qui tient dans votre semaine, et quelqu’un qui vous suit. C’est exactement la méthode Oblique.',
}

export const MARQUEE = ['PERSONAL TRAINING', 'COACHING EN ENTREPRISE', 'PRÉPARATION PHYSIQUE', 'NUTRITION']

export const METHOD = [
  {
    n: '01',
    title: 'Bilan',
    text: 'Objectifs, historique sportif, alimentation, rythme de vie : un bilan complet pour poser un point de départ précis. Le premier est offert.',
  },
  {
    n: '02',
    title: 'Plan sur mesure',
    text: 'Entraînement et nutrition construits pour vous, selon votre niveau, votre matériel et votre emploi du temps. Un plan que vous pouvez réellement tenir.',
  },
  {
    n: '03',
    title: 'Suivi & résultats',
    text: 'Points réguliers, mesures, ajustements. Le plan évolue avec vous jusqu’à l’objectif, puis vous aide à le garder.',
  },
]

export type Service = {
  id: string
  tag: string
  title: string
  text: string
  points: string[]
}

export const SERVICES: Service[] = [
  {
    id: 'domicile',
    tag: 'Particuliers',
    title: 'Personal training à domicile',
    text: 'Le coach vient à vous. Des séances individuelles chez vous, en extérieur ou en visio, calées sur votre niveau et votre agenda.',
    points: ['Bourges & alentours', 'Séances en ligne possibles', 'Programme 100 % individualisé'],
  },
  {
    id: 'entreprise',
    tag: 'DRH & dirigeants',
    title: 'Coaching en entreprise',
    text: 'Investissez dans la santé de vos équipes : prévention des troubles musculo-squelettiques et de l’absentéisme, bien-être au travail, cohésion.',
    points: ['Séances collectives sur site', 'Ateliers santé & nutrition', 'Formats adaptés à vos horaires'],
  },
  {
    id: 'prepa',
    tag: 'Sportifs',
    title: 'Préparation physique',
    text: 'Préparer une saison, une compétition ou un retour au jeu après le feu vert médical : force, puissance, endurance, prévention des blessures.',
    points: ['Tests & suivi de charge', 'Périodisation', 'Tous niveaux, tous sports'],
  },
  {
    id: 'nutrition',
    tag: 'Tous publics',
    title: 'Accompagnement nutritionnel',
    text: 'Des repères alimentaires concrets, adaptés à vos goûts et à votre rythme, pour soutenir vos objectifs sans régime extrême.',
    points: ['Habitudes durables', 'Composition corporelle', 'En complément de l’entraînement'],
  },
]

// Offre réelle du client (story Instagram « Challenge Oblique septembre »)
export const CHALLENGE = {
  title: 'Challenge Oblique',
  text: '4 mercredis pour retrouver la forme et reprendre le sport, en groupe.',
  next: '[Date de la prochaine session]', // [PLACEHOLDER]
}

// Note affichée au prospect pendant la phase de maquette. Passer enabled à false pour la mise en ligne.
export const PITCH = {
  enabled: true,
  title: 'Jahen, cette maquette a été conçue pour vous.',
  text: 'Vos couleurs, votre méthode, votre offre. Les éléments en pointillés attendent vos vraies informations : aucun avis ni chiffre n’a été inventé.',
  by: 'ScaleSync',
}

// value: nombre réel → compteur animé. value: null → placeholder visible.
export const STATS: { value: number | null; prefix?: string; suffix?: string; label: string; note?: string }[] = [
  { value: 30, prefix: '+', label: 'personnes accompagnées', note: 'Chiffre de la bio Instagram, à confirmer' },
  { value: null, label: 'séances réalisées' },
  { value: null, label: 'entreprises accompagnées' },
  { value: null, label: 'années d’expérience' },
]

export const ABOUT = {
  title: ['UN COACH.', 'UNE MÉTHODE.'],
  paragraphs: [
    'Je suis Jahen, coach sportif et expert en nutrition à Bourges. J’accompagne celles et ceux qui veulent reprendre le contrôle sur leur corps, leur santé et leurs performances.',
    'Ma méthode tient en une ligne : une méthode, un objectif, des résultats. Je pars de votre réalité, je construis un plan que vous pouvez tenir, et je reste à vos côtés jusqu’au résultat.',
  ],
  // [PLACEHOLDER] Parcours, diplômes et certifications réels
  story: '[Votre parcours en deux phrases : déclic, expérience, spécialités]',
  credentials: ['[Diplôme principal]', '[Certification nutrition]', '[Carte professionnelle n° …]'],
}

export const TESTIMONIALS = [
  { slot: 'Transformation · particulier' },
  { slot: 'Préparation physique · sportif' },
  { slot: 'Coaching en entreprise · équipe' },
]

export const ZONE = {
  radius: '[XX] km', // [PLACEHOLDER] rayon de déplacement réel
  towns: [
    // Positions approximatives (coordonnées réelles projetées) sur une carte 400×400 centrée sur Bourges.
    { name: 'Vierzon', x: 75, y: 122 },
    { name: 'Mehun-sur-Yèvre', x: 128, y: 167 },
    { name: 'Saint-Doulchard', x: 182, y: 184 },
    { name: 'Fussy', x: 198, y: 164 },
    { name: 'Les Aix-d’Angillon', x: 262, y: 133 },
    { name: 'Saint-Germain-du-Puy', x: 230, y: 192 },
    { name: 'Trouy', x: 196, y: 236 },
    { name: 'Saint-Florent-sur-Cher', x: 143, y: 252 },
    { name: 'Avord', x: 295, y: 228 },
  ],
}

export const FAQ = [
  {
    q: 'Comment se déroule la première séance ?',
    a: 'C’est un bilan, et il est offert. Nous faisons le point sur vos objectifs, votre historique sportif, votre alimentation et votre rythme de vie, puis quelques tests simples de mobilité et de condition physique. Vous repartez avec une vision claire de la marche à suivre, sans engagement.',
  },
  {
    q: 'Faut-il du matériel ou une salle de sport ?',
    a: 'Non. Les séances s’adaptent à votre espace et à ce que vous avez chez vous, en intérieur comme en extérieur. [À confirmer : matériel apporté par le coach.]',
  },
  {
    q: 'Quels sont vos tarifs ?',
    a: 'Les tarifs sont établis sur devis, selon la formule (séance à l’unité, pack, suivi mensuel), la fréquence et le lieu. Le bilan initial est offert : c’est le meilleur moyen d’obtenir une proposition précise.',
  },
  {
    q: 'Intervenez-vous en entreprise ?',
    a: 'Oui. Séances collectives sur site ou à proximité, ateliers santé et nutrition, programmes sur plusieurs semaines. Le format est construit avec la direction ou les RH selon vos objectifs : bien-être, prévention, cohésion d’équipe.',
  },
  {
    q: 'La nutrition est-elle incluse dans le coaching ?',
    a: 'L’accompagnement nutritionnel peut être intégré à votre suivi ou pris séparément. Il porte sur des habitudes alimentaires durables au service de vos objectifs. En cas de pathologie, il se fait en complément de votre médecin ou d’un diététicien.',
  },
]

export const LEGAL = {
  // [PLACEHOLDER] Mentions légales réelles
  lines: [
    'Éditeur : [Raison sociale / nom] · [Statut juridique] · SIRET [XXX XXX XXX XXXXX]',
    'Adresse : [Adresse professionnelle], Bourges',
    'Hébergement : Vercel Inc., 340 S Lemon Ave #4133, Walnut, CA 91789, USA',
    'Contact : [contact@oblique-coaching.fr]',
  ],
}
