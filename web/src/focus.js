/** Getting a sharp frame out of a live camera.
 *
 *  Shared by the two places in this app that take a picture themselves — the
 *  card scanner and the guided camera — because they had the same bug and
 *  would have grown apart fixing it separately. The third way to photograph
 *  something, the ordinary "Take photo" button, hands off to the phone's own
 *  camera app and needs none of this: it already has autofocus, a shutter and
 *  a person who knows how to use both.
 *
 *  The problem both had: pressing the button grabbed whatever frame was on
 *  screen at that instant. A hand is never quite still and autofocus is
 *  always a beat behind, so a press during the wrong 30 milliseconds sent a
 *  smear — with nothing to say it had, because a blurred photo looks fine
 *  until you try to read it.
 */

/** Ask a camera to keep focusing rather than hold the distance it opened at.
 *
 *  Best-effort by design. Plenty of devices expose no focus control at all,
 *  and some advertise the capability and then refuse the constraint; neither
 *  is worth an error, because the burst below is what actually carries this.
 */
export async function keepFocusing(track) {
  if (!track) return;
  try {
    const modes = track.getCapabilities?.().focusMode || [];
    if (modes.includes("continuous")) {
      await track.applyConstraints({ advanced: [{ focusMode: "continuous" }] });
    }
  } catch {
    /* a camera that refuses focus constraints still takes pictures */
  }
}

/** How much detail a frame has, as gradient energy.
 *
 *  A blurred picture is the same picture with its edges smeared, so
 *  neighbouring pixels agree more. Squaring the differences rewards a few
 *  crisp edges over many gentle ones, which is what separates a focused card
 *  from a soft one.
 *
 *  Scored on a small copy: a hundred and twenty pixels across is plenty to
 *  tell focus from blur and cheap enough to run on every frame, where the
 *  full-resolution photo the guided camera keeps would not be.
 *
 *  Only ever compared against other frames of the same scene. The number
 *  moves with lighting, with framing, and with how busy the subject is, so
 *  "sharper than the one before it" means something where "sharper than 40"
 *  would be nonsense in a dim room.
 */
export function sharpness(source, scratch) {
  const cv = scratch;
  const ctx = cv.getContext("2d", { willReadFrequently: true });
  ctx.drawImage(source, 0, 0, cv.width, cv.height);
  const { data, width, height } = ctx.getImageData(0, 0, cv.width, cv.height);
  const grey = (i) => data[i] * 0.299 + data[i + 1] * 0.587 + data[i + 2] * 0.114;
  let sum = 0;
  for (let y = 1; y < height; y++) {
    for (let x = 1; x < width; x++) {
      const i = (y * width + x) * 4;
      const dx = grey(i) - grey(i - 4);
      const dy = grey(i) - grey(i - width * 4);
      sum += dx * dx + dy * dy;
    }
  }
  return sum / (width * height);
}

/** A scratch canvas for scoring, made once per camera. */
export function scratchCanvas(ratio = 5 / 7) {
  const cv = document.createElement("canvas");
  cv.width = 120;
  cv.height = Math.round(120 / ratio);
  return cv;
}

/** The sharpest of a few frames taken a moment apart.
 *
 *  `grab` returns a canvas of the current frame, or null if there isn't one
 *  yet. Only the best is kept, so however many frames are sampled at most
 *  two exist at once — which matters where the frames are full-resolution
 *  photographs rather than thumbnails.
 */
export async function sharpestOf(grab, scratch, count = 6, gap = 110) {
  let best = null;
  let bestScore = -1;
  for (let i = 0; i < count; i++) {
    const frame = grab();
    if (frame) {
      const score = sharpness(frame, scratch);
      if (score > bestScore) {
        bestScore = score;
        best = frame;
      }
    }
    if (i < count - 1) {
      await new Promise((r) => setTimeout(r, gap));
    }
  }
  return best;
}
