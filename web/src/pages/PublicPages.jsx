import { Link } from "react-router-dom";
import { BrandMark } from "../components/Icons.jsx";

/** The pages a stranger has to be able to read.
 *
 *  Deliberately outside the sign-in gate — see SignIn.jsx. Google Play
 *  requires both a privacy policy and a way to ask for deletion at addresses
 *  that work without installing anything or holding an account, and a policy
 *  you can only read once you have already signed up is no policy at all.
 *
 *  These describe the hosted service. A self-hosted install has no operator
 *  but the person running it, and none of this applies to it.
 */

// One date for all three, because they were written together and a reader
// comparing them should not have to wonder which is newest.
const UPDATED = "15 August 2026";
const CONTACT = "support@yourloot.app";

function PublicDoc({ title, children }) {
  return (
    <div className="public-doc">
      <header>
        <Link to="/" className="public-brand">
          <BrandMark size={22} />
          Your <b>Loot</b>
        </Link>
        <h1>{title}</h1>
        <p className="public-updated">Last updated {UPDATED}</p>
      </header>
      {children}
      <footer className="public-foot">
        <Link to="/privacy">Privacy</Link>
        <Link to="/terms">Terms</Link>
        <Link to="/delete-account">Delete your account</Link>
        <Link to="/">Sign in</Link>
      </footer>
    </div>
  );
}

export function DeleteAccountPage() {
  return (
    <PublicDoc title="Deleting your account">
      <p>
        You can delete your Your Loot account and everything in it at any time,
        from inside the app. You do not need to ask us, and we do not ask why.
      </p>

      <h2>If you can sign in</h2>
      <ol>
        <li>Sign in at <Link to="/">yourloot.app</Link></li>
        <li>Go to <strong>Settings</strong></li>
        <li>Under <strong>Your account</strong>, choose <strong>Delete this account</strong></li>
        <li>Confirm with your password</li>
      </ol>
      <p>
        It happens immediately. Take a copy first if you want one —
        <strong> Settings → Share a collection</strong> gives you a file with
        everything in it. Afterwards there is nothing to take one from.
      </p>

      <h2>If you cannot sign in</h2>
      <p>
        Email <a href={`mailto:${CONTACT}`}>{CONTACT}</a> from the address on the
        account and ask us to delete it. We will confirm before we do anything,
        and we will not act on a request that does not come from that address —
        otherwise anyone who knew your email could delete your collection.
      </p>

      <h2>What deletion removes</h2>
      <ul>
        <li>Your account: email address, password, display name</li>
        <li>Everything you own or want, with its conditions, grades and notes</li>
        <li>Your binders and how you arranged them</li>
        <li>Your tags and your settings</li>
        <li>Photographs you uploaded</li>
        <li>Any access tokens you created</li>
      </ul>

      <h2>What stays, and why</h2>
      <p>
        The shared catalogue — the cards, games, books and records themselves —
        is not yours and is not deleted. It is the same list for everybody and
        holds nothing about you. The same is true of the barcode lookups the
        service caches: those record what a barcode is, not who scanned it.
      </p>
      <p>
        Deleted data can survive in encrypted database backups for up to
        <strong> 30 days</strong>, after which those backups expire and it is
        gone from those too. We do not restore an individual account from a
        backup after deletion, and we cannot undo a deletion for you.
      </p>

      <h2>Self-hosting</h2>
      <p>
        Your Loot is open source and many people run their own copy. If your
        collection lives on somebody else's server rather than on yourloot.app,
        this page does not apply — ask whoever runs it.
      </p>
    </PublicDoc>
  );
}

export function PrivacyPage() {
  return (
    <PublicDoc title="Privacy">
      <p>
        Your Loot is a place to keep track of things you own. It is run by a
        very small operation, it is paid for by subscriptions rather than
        advertising, and it therefore has no reason to learn anything about you
        beyond what it takes to show you your own collection.
      </p>
      <p className="public-lead">
        <strong>There is no analytics, no tracking, and no advertising on this
        service.</strong> Nothing you do here is measured, profiled or sold, and
        we do not share your collection with anyone.
      </p>

      <h2>What we store</h2>
      <div className="public-table"><table>
        <tbody>
          <tr><th>What</th><th>Why</th></tr>
          <tr><td>Your email address</td><td>To sign you in, confirm the address is yours, and send a reset link if you forget your password</td></tr>
          <tr><td>Your password</td><td>Stored only as an argon2id hash. We cannot read it, and neither can anybody who takes a copy of the database</td></tr>
          <tr><td>Display name, if you set one</td><td>To greet you by name. Optional, and it can be anything</td></tr>
          <tr><td>Your collection</td><td>The items, copies, conditions, grades, notes, tags, wanted list and binders you enter. This is the service</td></tr>
          <tr><td>Photographs you upload</td><td>Shown on your own items, to you</td></tr>
          <tr><td>Access tokens you create</td><td>Only as a hash, so a stolen database is not a set of working keys</td></tr>
        </tbody>
      </table></div>
      <p>
        We do not ask for your real name, your address, your date of birth or a
        payment card. If subscriptions are offered, card details go directly to
        the payment processor and never reach our servers.
      </p>

      <h2>Cookies</h2>
      <p>
        One cookie, and it is how you stay signed in. It is signed, marked
        http-only so scripts cannot read it, sent only to this site, and lasts
        thirty days. There are no advertising or analytics cookies, which is why
        this site does not put a consent banner in front of you — a cookie that
        is strictly necessary to do the thing you asked for does not require
        one.
      </p>
      <p>
        The app also keeps two things in your browser's own storage, and only if
        you put them there: an access token, if you created one, and the address
        of a different server, if you pointed the app at one. Neither is sent
        anywhere except the server you chose.
      </p>

      <h2>Who else sees anything</h2>
      <p>
        Four kinds of third party are involved, and it is worth being precise
        about which sees what.
      </p>
      <div className="public-table"><table>
        <tbody>
          <tr><th>Who</th><th>What reaches them</th></tr>
          <tr><td>Our hosting provider</td><td>Runs the servers and the database. They hold your data on our behalf and may not use it for anything else</td></tr>
          <tr><td>Our email provider</td><td>Your email address and the text of the two messages this service sends: confirm your address, and reset your password</td></tr>
          <tr><td>Catalogue sources</td><td>When you search for a card, game, book or record, the words you searched for are sent to that catalogue so it can answer. Your identity is not — the request comes from our server, not from you</td></tr>
          <tr><td>Image hosts</td><td>Cover art and card scans are loaded by your browser directly from the projects that publish them, so those hosts can see your IP address, as they would for any image on any website</td></tr>
        </tbody>
      </table></div>
      <p>
        We do not sell data, and there is nothing here that would be worth
        selling. We will hand over data if a court makes us, and we will tell you
        if we are allowed to.
      </p>

      <h2>How long we keep it</h2>
      <p>
        Your collection stays until you delete it or your account. When you
        delete your account it goes immediately, and disappears from encrypted
        backups within thirty days. See <Link to="/delete-account">deleting your
        account</Link>, which you can do yourself without asking us.
      </p>

      <h2>Your rights</h2>
      <p>
        You can take a complete copy of everything you have entered at any time
        from <strong>Settings → Share a collection</strong> — a single file, no
        request and no waiting, and it includes collections your plan no longer
        opens. You can correct anything by editing it, and delete everything by
        deleting your account. If you would rather ask us to do any of that,
        write to <a href={`mailto:${CONTACT}`}>{CONTACT}</a>.
      </p>
      <p>
        Depending on where you live you may also have the right to object to
        processing, to complain to a data protection authority, or to ask for
        your data in a portable form — the backup file is that.
      </p>

      <h2>Children</h2>
      <p>
        This service is not intended for children under 13, and we do not
        knowingly hold data about them. If you believe a child has an account
        here, write to us and we will remove it.
      </p>

      <h2>Security</h2>
      <p>
        Passwords are hashed with argon2id. Traffic is encrypted in transit.
        Sessions are signed and http-only. Accounts cannot see each other's
        collections, which is enforced in the code and covered by tests that run
        before every release. No service is perfect; if you find a problem,
        please tell us before you tell anyone else.
      </p>

      <h2>Self-hosted copies</h2>
      <p>
        Your Loot is open source and anybody may run it. This policy covers
        yourloot.app only. If your collection is on somebody else's server, they
        are the ones holding it and this document says nothing about what they
        do.
      </p>

      <h2>Changes</h2>
      <p>
        If this policy changes in a way that matters, we will say so by email
        before it takes effect rather than quietly changing the date at the top.
      </p>
    </PublicDoc>
  );
}

export function TermsPage() {
  return (
    <PublicDoc title="Terms of service">
      <p>
        These are the terms for using yourloot.app. They are meant to be read,
        so they are short.
      </p>

      <h2>What this is</h2>
      <p>
        A place to catalogue things you own — cards, games, books, records and
        the rest. You enter what you have; it keeps track of it and shows it back
        to you.
      </p>

      <h2>Your account</h2>
      <p>
        Use an email address you actually control, because it is how you get back
        in. Keep your password to yourself. You are responsible for what happens
        under your account. You must be at least 13 years old.
      </p>
      <p>
        You can leave whenever you like and take your collection with you — see
        <Link to="/delete-account"> deleting your account</Link>.
      </p>

      <h2>What you enter is yours</h2>
      <p>
        Your collection, your notes and your photographs belong to you. You give
        us only the permission needed to store them and show them back to you,
        and to whoever you deliberately share an export with. We do not claim
        ownership, we will not use your photographs for anything else, and we
        will not train anything on your data.
      </p>

      <h2>What the catalogue is</h2>
      <p>
        Titles, cover art, card scans and descriptions come from public
        catalogues and belong to their publishers and rights holders, not to us
        and not to you. They are here so you can identify what you own. Nothing
        in this service grants you any right to that material.
      </p>

      <h2>Fair use of the service</h2>
      <p>Please do not:</p>
      <ul>
        <li>break into other people's accounts, or try to</li>
        <li>scrape the catalogue wholesale or hammer the service with automation</li>
        <li>upload anything unlawful, or anything you have no right to upload</li>
        <li>resell access to the service</li>
      </ul>
      <p>
        We may suspend an account doing any of that. If it looks like a mistake
        rather than malice, we will ask first.
      </p>

      <h2>If you subscribe</h2>
      <p>
        Paid plans, where offered, are billed in advance through our payment
        processor and renew until you cancel. Cancel whenever you like; the plan
        runs to the end of the period you have paid for and does not renew. If
        something goes wrong within the first thirty days, write to us and we
        will refund you. Prices can change, but not for a period you have already
        paid for, and we will give notice before a renewal at a new price.
      </p>
      <p>
        If a paid feature stops being available for reasons outside our control —
        a data source withdrawing access, say — we will tell you and refund the
        unused part of your subscription.
      </p>

      <h2>What we promise, and what we do not</h2>
      <p>
        We will look after your data, keep the service running, and give you a
        way to take a complete copy of it whenever you want. That last one is the
        real promise: <strong>your collection is never trapped here.</strong>
      </p>
      <p>
        We cannot promise the service is never down, never has a bug, or is
        available forever. It is provided as it is, without warranties. To the
        extent the law allows, our liability is limited to what you have paid us
        in the last twelve months — and if you are on the free plan, that is
        nothing, which is the honest bargain of a free plan.
      </p>
      <p>
        <strong>Keep your own backups.</strong> The export exists so that you
        can, and it would be unwise to treat any single service as the only copy
        of something you care about.
      </p>

      <h2>Ending it</h2>
      <p>
        You can delete your account at any time. We can close an account that
        breaks these terms. If we ever shut the service down, we will give at
        least thirty days' notice so everybody can take their collection with
        them.
      </p>

      <h2>The legal bits</h2>
      <p>
        These terms are governed by the laws of Tennessee, United States. If part
        of them turns out to be unenforceable, the rest still stands. If they
        change materially we will tell you before the change takes effect.
      </p>
      <p>
        Questions: <a href={`mailto:${CONTACT}`}>{CONTACT}</a>
      </p>
    </PublicDoc>
  );
}
