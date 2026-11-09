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
  spanish: `de la que el en y a los del se las por un para con no una su al lo como más pero sus le ya o fue este ha sí
    porque esta son entre cuando muy sin sobre también me hasta hay donde quien desde todo nos durante todos uno les ni
    contra otros ese eso ante ellos esto mí antes algunos qué unos yo otro otras otra tanto esa estos mucho quienes nada
    muchos cual poco ella estar estas algunas algo nosotros mi mis tú te ti tu tus ella ellas vosotros os mío mía tuyo
    suyo nuestro vuestro ser haber estar`,
  french: `au aux avec ce ces dans de des du elle en et eux il je la le leur lui ma mais me même mes moi mon ne nos notre
    nous on ou par pas pour qu que qui sa se ses son sur ta te tes toi ton tu un une vos votre vous y a ai as ont été être
    suis es est sommes êtes sont était étaient sera serait avoir avait ont plus moins très aussi si ne pas ni ou car donc
    dans chez vers sans sous entre pendant avant après tout tous toute toutes cette cet ça cela celui celle ceux dont où
    quand comment pourquoi`,
  portuguese: `de a o que e do da em um para é com não uma os no se na por mais as dos como mas foi ao ele das tem à seu
    sua ou ser quando muito há nos já está eu também só pelo pela até isso ela entre era depois sem mesmo aos tem seus
    quem nas me esse eles estão você tinha foram essa num nem suas meu às minha têm numa pelos elas havia seja qual
    será nós tenho lhe deles essas esses pelas este fosse dele tu nós vos lhe`,
  italian: `di a da in che e il lo la i le un una del della dei delle al allo alla ai agli nel nella nei nelle con per su tra
    fra non si ma o come anche più questo questa questi queste quello quella quelli quelle io tu lui lei noi voi loro
    mio mia miei mie tuo tua suoi sue nostro nostra è sono era erano essere stato stata stati state ha hanno aveva
    avevano c'è ci ne gli se perché quando dove chi cosa quale`,
  dutch: `de het een van en in is dat op te zijn voor met als aan er maar om dit niet die zo dan nog wel geen tot ook al was
    bij uit naar over je jij wij we zij hij hun hen mijn zijn haar ons jullie deze daar hier waar wanneer waarom hoe wat
    wie welke welk of want toch steeds altijd nooit iets niets alles iedereen iemand niemand kan moet mag zou hebben
    had heeft werd worden wordt`,
  russian: `и в во не что он на я с со как а то все она так его но да ты к у же вы за бы по только ее мне было вот от меня еще
    нет о из ему теперь когда даже ну ли если уже или ни быть был него до вас уж вам ведь там потом себя ничего ей может
    они тут где есть надо ней для мы тебя их чем была сам чтоб без будто чего раз тоже себе под будет тогда кто этот
    потому этого какой совсем ним здесь этом один почти мой тем чтобы нее сейчас были куда зачем всех никогда сегодня
    можно при наконец два об другой хоть после над больше тот через эти нас про всего них какая много три эту моя перед
    иногда лучше чуть том нельзя такой им более всегда конечно всю между`,
  arabic: `في من على إلى عن أن إن هذا هذه تلك ذلك ما لا لم لن قد كان كانت يكون تكون هو هي هم هن نحن أنت أنتم التي الذي الذين
    و أو ثم بل لكن إذا إذ حيث كيف متى أين لماذا مع بين تحت فوق قبل بعد كل بعض غير سوى حتى عند لدى منذ خلال ضد دون أي
    هناك هنا أيضا فقط ليس ليست ليسوا`,
  hindi: `का के की में है हैं था थे थी को से पर ने यह वह और या कि जो तो भी नहीं ही एक लिए गया गई गए हो हम आप मैं तुम वे उनका
    उनकी उसके इसकी इसके इन उन कोई कुछ सब जब तक अगर तो इसलिए क्योंकि यहाँ वहाँ अब फिर बहुत कम अधिक`,
  indonesian: `yang dan di ke dari untuk pada adalah dengan ini itu atau sebagai juga tidak ada oleh akan antara sudah belum
    lebih sangat dapat bisa harus kami kita saya anda mereka dia ia nya serta maupun telah sedang pun bagi bagi
    kepada daripada tentang dalam atas bawah`,
  polish: `i w z na do że się nie to jest jak o a po co za od dla ale czy jej mu ich tym ten tej tych już też tylko jeszcze
    by był była było były będzie są być mnie mi mój moja moje nas nasz jego tu tam kiedy gdzie kto co jaki która które
    który jeśli choć albo lub oraz przy pod nad przez między`,
};

export const STOPWORD_LANGUAGES = {
  danish: "Dansk · Danish",
  english: "Engelsk · English",
  spanish: "Spansk · Spanish",
  french: "Fransk · French",
  arabic: "Arabisk · Arabic",
  portuguese: "Portugisisk · Portuguese",
  russian: "Russisk · Russian",
  german: "Tysk · German",
  hindi: "Hindi",
  indonesian: "Indonesisk · Indonesian",
  italian: "Italiensk · Italian",
  dutch: "Nederlandsk · Dutch",
  polish: "Polsk · Polish",
  swedish: "Svensk · Swedish",
  norwegian: "Norsk · Norwegian",
  finnish: "Finsk · Finnish",
  all: "Alle disse · All of these",
};

export const DEFAULT_STOPWORD_LANGUAGE = "danish";

const SETS = Object.fromEntries(
  Object.entries(LISTS).map(([lang, words]) => [lang, new Set(words.replace(/"/g, "").split(/\s+/).filter(Boolean))]),
);

export function stopwordSet(language = "english") {
  if (language === "all") return new Set(Object.values(SETS).flatMap((s) => [...s]));
  return SETS[language] ?? SETS.english;
}
