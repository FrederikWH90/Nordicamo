// Common function words per language (in the spirit of the widely used
// NLTK/Snowball lists). Lower case; matched after tokenizing.

const LISTS = {
  english: `a about above after again against all am an and any are aren't as at be because been before being below
    between both but by can can't cannot could couldn't did didn't do does doesn't doing don't down during each few for
    from further had hadn't has hasn't have haven't having he he'd he'll he's her here here's hers herself him himself his
    how how's i i'd i'll i'm i've if in into is isn't it it's its itself let's me more most mustn't my myself no nor not of
    off on once only or other ought our ours ourselves out over own same shan't she she'd she'll she's should shouldn't so
    some such than that that's the their theirs them themselves then there there's these they they'd they'll they're
    they've this those through to too under until up very was wasn't we we'd we'll we're we've were weren't what what's
    when when's where where's which while who who's whom why why's will with won't would wouldn't you you'd you'll you're
    you've your yours yourself yourselves also just said says one two now new like get got even much many may might
    must still yet well back way since around however"`,
  danish: `og i jeg det at en den til er som på de med han af for ikke der var mig sig men et har om vi min havde ham hun
    nu over da fra du ud sin dem os op man hans hvor eller hvad skal selv her alle vil blev kunne ind når være dog noget
    ville jo deres efter ned skulle denne end dette mit også under have dig anden hende mine alt meget sit sine vor mod
    disse hvis din nogle hos blive mange ad bliver hendes været thi jer sådan kan sagde siger får fik bare mere mest
    hele helt lige blandt flere første andre andet både uden ved så ja nej altså derfor fordi mens før igen altid
    aldrig blevet haft gjort går gik kom kommer omkring mellem gennem imod ifølge samt blot kun siden allerede stadig`,
  swedish: `och det att i en jag hon som han på den med var sig för så till är men ett om hade de av icke mig du henne då
    sin nu har inte hans honom skulle hennes där min man ej vid kunde något från ut när efter upp vi dem vara vad över än
    dig kan sina här ha mot alla under någon eller allt mycket sedan ju denna själv detta åt utan varit hur ingen mitt ni
    bli blev oss din dessa några deras blir mina samma vilken er sådan vår blivit dess inom mellan sådant varför varje
    vilka ditt vem vilket sitta sådana vart dina vars vårt våra ert era vilkas också mer bara sa säger får fick andra
    flera första hela helt både`,
  norwegian: `og i jeg det at en et den til er som på de med han av ikke ikkje der så var meg seg men ett har om vi min mitt
    ha hadde hun nå over da ved fra du ut sin dem oss opp man kan hans hvor eller hva skal selv sjøl her alle vil bli ble
    blei blitt kunne inn når være kom noen noe ville dere som deres kun ja etter ned skulle denne for deg si sine sitt mot
    å meget hvorfor dette disse uten hvordan ingen din ditt blir samme hvilken hvilke sånn inni mellom vår hver hvem vors
    hvis både bare enn fordi før mange også slik vært være båe begge siden dykk dykkar dei deira deires deim di då eg ein
    eit eitt elles honom hjå ho hoe henne hennar hennes hoss hossen ikkje ingi inkje korleis korso kva kvar kvarhelst
    kven kvi kvifor me medan mi mine mykje no nokon noka nokor noko nokre si sia sidan so somt somme um upp vere vore
    verte vort varte vart sa sier får fikk andre flere første hele helt`,
  finnish: `olla olen olet on olemme olette ovat ole oli olisi olisit olisin olisimme olisitte olisivat olit olin olimme
    olitte olivat ollut olleet en et ei emme ette eivät minä minun minut minua minussa minusta minuun minulla minulta
    minulle sinä sinun sinut sinua sinussa sinusta sinuun sinulla sinulta sinulle hän hänen hänet häntä hänessä hänestä
    häneen hänellä häneltä hänelle me meidän meidät meitä meissä meistä meihin meillä meiltä meille te teidän teidät
    teitä teissä teistä teihin teillä teiltä teille he heidän heidät heitä heissä heistä heihin heillä heiltä heille tämä
    tämän tätä tässä tästä tähän tällä tältä tälle tänä täksi tuo tuon tuota tuossa tuosta tuohon tuolla tuolta tuolle
    tuona tuoksi se sen sitä siinä siitä siihen sillä siltä sille sinä siksi nämä näiden näitä näissä näistä näihin
    näillä näiltä näille ninä niiksi nuo noiden noita noissa noista noihin noilla noilta noille noina noiksi ne niiden
    niitä niissä niistä niihin niillä niiltä niille niinä niiksi kuka kenen kenet ketä kenessä kenestä keneen kenellä
    keneltä kenelle kenenä keneksi ketkä keiden keitä keissä keistä keihin keillä keiltä keille keinä keiksi mikä minkä
    mitä missä mistä mihin millä miltä mille minä miksi mitkä joka jonka jota jossa josta johon jolla jolta jolle jona
    joksi jotka joiden joita joissa joista joihin joilla joilta joille joina joiksi että ja jos koska kuin mutta niin sekä
    sillä tai vaan vai vaikka kanssa mukaan noin poikki yli kun niin nyt itse myös vain sitten jo vielä sanoi`,
  german: `aber alle allem allen aller alles als also am an ander andere anderem anderen anderer anderes anderm andern
    anderr anders auch auf aus bei bin bis bist da damit dann der den des dem die das dass daß derselbe derselben
    denselben desselben demselben dieselbe dieselben dasselbe dazu dein deine deinem deinen deiner deines denn derer
    dessen dich dir du dies diese diesem diesen dieser dieses doch dort durch ein eine einem einen einer eines einig
    einige einigem einigen einiger einiges einmal er ihn ihm es etwas euer eure eurem euren eurer eures für gegen gewesen
    hab habe haben hat hatte hatten hier hin hinter ich mich mir ihr ihre ihrem ihren ihrer ihres euch im in indem ins ist
    jede jedem jeden jeder jedes jene jenem jenen jener jenes jetzt kann kein keine keinem keinen keiner keines können
    könnte machen man manche manchem manchen mancher manches mein meine meinem meinen meiner meines mit muss musste nach
    nicht nichts noch nun nur ob oder ohne sehr sein seine seinem seinen seiner seines selbst sich sie ihnen sind so
    solche solchem solchen solcher solches soll sollte sondern sonst über um und uns unsere unserem unseren unser
    unseres unter viel vom von vor während war waren warst was weg weil weiter welche welchem welchen welcher welches
    wenn werde werden wie wieder will wir wird wirst wo wollen wollte würde würden zu zum zur zwar zwischen`,
};

export const STOPWORD_LANGUAGES = {
  danish: "Dansk",
  english: "Engelsk",
  swedish: "Svensk",
  norwegian: "Norsk",
  finnish: "Finsk",
  german: "Tysk",
  all: "Alle disse",
};

export const DEFAULT_STOPWORD_LANGUAGE = "danish";

const SETS = Object.fromEntries(
  Object.entries(LISTS).map(([lang, words]) => [lang, new Set(words.replace(/"/g, "").split(/\s+/).filter(Boolean))]),
);

export function stopwordSet(language = "english") {
  if (language === "all") return new Set(Object.values(SETS).flatMap((s) => [...s]));
  return SETS[language] ?? SETS.english;
}
