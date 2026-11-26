import type { EventListItem } from './data';
import { storeApp } from './features';

/**
 * App VendrediParty de l'App Store (refus Apple 1.4.3, 25.11) : un événement PUBLIC dont le titre, la description, le lieu
 * ou les mini-sondages parlent d'alcool, d'ivresse ou de drogue n'apparaît ni dans la liste ni dans la recherche de l'app.
 * Ses invités, ses participants et son organisation le voient toujours ; le site, l'app BETA et Android aussi.
 * Même liste de mots que le serveur (DRINK_RE, app/store_app.py ; test tests/test_store_app.py).
 */
export const DRINK_RE = new RegExp(
  [
    'gorg[ée]es?', '\\bboire\\b', '\\bboi[st]\\b', '\\bboivent\\b', '\\bbuvez\\b', '\\bbu\\b', '\\bshots?\\b', 'alcool', 'bi[èe]res?\\b',
    '\\bvins?\\b', 'vodka', 'tequila', 'whisky', '\\brhums?\\b', '\\bgin\\b', '\\btourn[ée]es?\\b', '\\bcuites?\\b', '\\bivres?\\b', 'ivresse',
    'bourr[ée]e?s?\\b', 'gueule de bois', 'ap[ée]ro', 'cocktail', 'champagne', 'mojito', 'ca[iï]pirinha', 'sangria', 'spritz', 'pastis',
    'j[äa]germeister', 'liqueur', '\\bbars?\\b', '\\bverres?\\b', 'drogue', 'cannabis', 'coca[iï]ne', '\\bjoint\\b', 'ecstasy', 'mdma',
    '\\blsd\\b', 'cigarette', 'nicotine', '\\bvomi', 'tchin', 'beer', 'bouteilles?', '🍻', '🍺', '🥃', '🍸', '🍹', '🍷', '🍾', '🥂',
    // Ajoutés le 25.11 (vins, alcools, régions viticoles, tabac, casino, drogue dans les titres d'œuvres).
    'ap[ée]ritif','arros[ée]','pot de d[ée]part','buvette','\\bboirai','cuv[ée]e','vigneron','vendange','viticole','vignoble','c[ée]page','absinthe','tabac','casino','poker','blackjack','cidre','\\bkir\\b','kirsch','cognac','calvados','armagnac','grappa','\\bsak[ée]\\b','prosecco','\\bcava\\b','guinness','eau-de-vie','eaux-de-vie','damassine','fendant','chasselas','merlot','pinot','chouchen','soju','baijiu','limoncello','ouzo','campari','aperol','cacha[çc]a','bourbon','cervoise','[ée]thanol','porto\\b','bordeaux','bourgogne','beaujolais','chardonnay','sauvignon','riesling','lambrusco','chianti','rioja','brasserie','brasseur','houblon','malt\\b','distill','spiritueux','digestif','\\braki\\b','mezcal','chartreuse','fernet','pimm','\\bkvas\\b','barolo','gamay','syrah','cornalin','humagne','d[ée]zaley','\\bperlan\\b','johannisberg','arvine','perdrix','amaretto','poire williams','ros[ée] de provence','gin-tonic','trafiquant','narcos','escobar','\\bweeds\\b','breaking bad','trainspotting','\\bcoke\\b','h[ée]ro[iï]ne\\b','\\bcrack\\b','opium','dealer',
    // Ajoutés au tour 6 (25.11) : mots courants d'un titre de soirée, tabac et vapotage (1.4.3).
    'happy hour','after-?work','\\bpintes?\\b','oktoberfest','ti-?punch','binouze','pub crawl','margarita','\\bshooters?\\b','ricard','heineken','chicha','narguil[ée]','\\bvapot','\\bvape\\b','\\bpuffs?\\b','\\bj[äa]ger\\b','\\bpils\\b','\\bipa\\b',
  ].join('|'),
  'iu',
);

type StoreFields = {
  polls?: { question: string; poll_options?: { label: string }[] }[];
  bring_items?: { label: string }[];
  event_organizers?: { user_id: string }[];
  event_invites?: { user_id: string }[];
};

export const STORE_EVENT_EXTRA = ', polls(question, poll_options(label)), bring_items(label), event_organizers(user_id), event_invites(user_id)';

export function drinkyEvent(e: EventListItem & StoreFields): boolean {
  const texts = [e.title, e.description, e.location_name, ...(e.polls ?? []).flatMap((p) => [p.question, ...(p.poll_options ?? []).map((o) => o.label)]),
    ...(e.bring_items ?? []).map((b) => b.label)];
  return texts.some((t) => !!t && DRINK_RE.test(t));
}

/** Les événements que l'app App Store montre : tout, sauf un événement public « à boisson » où je ne suis pour rien. */
export function storeVisible<T extends EventListItem>(events: T[], me: string | null | undefined): T[] {
  if (!storeApp) return events;
  return events.filter((raw) => {
    const e = raw as T & StoreFields;
    if (e.visibility !== 'all' || !drinkyEvent(e)) return true;
    return !!me && (e.created_by === me || e.rsvps.some((r) => r.user_id === me)
      || (e.event_organizers ?? []).some((o) => o.user_id === me) || (e.event_invites ?? []).some((i) => i.user_id === me));
  });
}
