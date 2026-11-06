export function compressionReduction(levelDb, threshold, ratio, knee) {
  const over = levelDb - threshold, slope = 1 - 1 / ratio;
  if (knee > 0 && over > -knee / 2 && over < knee / 2) return slope * (over + knee / 2) ** 2 / (2 * knee);
  return over > 0 ? slope * over : 0;
}
// RMS-детектор 5 мс; общая огибающая каналов сохраняет стереопанораму.
export class CompressorCore {
  constructor(rate) { this.rate = rate; this.detector = Math.exp(-1 / (rate * .005)); this.energy = 0; this.reduction = 0; }
  configure({ threshold, ratio, knee, attack, release, makeup, mix }) {
    Object.assign(this, { threshold, ratio, knee, makeup, mix });
    this.attackCoefficient = Math.exp(-1 / (this.rate * attack / 1000));
    this.releaseCoefficient = Math.exp(-1 / (this.rate * release / 1000));
  }
  processFrame(left, right) {
    this.energy = this.detector * this.energy + (1 - this.detector) * Math.max(left * left, right * right);
    const desired = compressionReduction(10 * Math.log10(Math.max(1e-16, this.energy)), this.threshold, this.ratio, this.knee);
    const coefficient = desired > this.reduction ? this.attackCoefficient : this.releaseCoefficient;
    this.reduction = desired + coefficient * (this.reduction - desired);
    return 1 - this.mix + this.mix * 10 ** ((this.makeup - this.reduction) / 20);
  }
  reset() { this.energy = 0; this.reduction = 0; }
}
