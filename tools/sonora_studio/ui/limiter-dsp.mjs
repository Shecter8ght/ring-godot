// Связанный стереолимитер: общий коэффициент сохраняет панораму и запас до пика.
export class LimiterCore {
  constructor(rate, lookahead = .005) {
    this.rate = rate; this.delay = Math.max(1, Math.round(rate * lookahead)); this.size = this.delay + 2;
    this.left = new Float32Array(this.size); this.right = new Float32Array(this.size);
    this.peaks = new Float64Array(this.size); this.indices = new Float64Array(this.size);
    this.head = 0; this.tail = 0; this.frame = 0; this.gain = 1; this.outputL = 0; this.outputR = 0;
  }
  processFrame(left, right, drive, ceiling, recovery, enabled) {
    const frame = this.frame++, slot = frame % this.size;
    const l = left, r = right;
    this.left[slot] = l; this.right[slot] = r;
    while (this.head !== this.tail && this.indices[this.head] < frame - this.delay) this.head = (this.head + 1) % this.size;
    const peak = Math.max(Math.abs(l), Math.abs(r));
    while (this.head !== this.tail && this.peaks[(this.tail + this.size - 1) % this.size] <= peak) this.tail = (this.tail + this.size - 1) % this.size;
    this.peaks[this.tail] = peak; this.indices[this.tail] = frame; this.tail = (this.tail + 1) % this.size;
    const required = enabled ? Math.min(1, ceiling / Math.max(1e-12, this.peaks[this.head] * drive)) : 1;
    this.gain = !enabled ? 1 : required < this.gain ? required : required + (this.gain - required) * recovery;
    const read = (frame - this.delay + this.size) % this.size;
    const outputGain = this.gain * (enabled ? drive : 1);
    this.outputL = frame < this.delay ? 0 : this.left[read] * outputGain;
    this.outputR = frame < this.delay ? 0 : this.right[read] * outputGain;
    return this.gain;
  }
}
