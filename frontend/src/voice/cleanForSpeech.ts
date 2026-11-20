/**
 * Prépare un texte de l'agent pour la synthèse vocale : sans SQL, sans Markdown, unités lues en toutes
 * lettres. Le texte complet reste affiché à l'écran.
 */
export function cleanForSpeech(text: string, maxChars = 700): string {
  let t = text
    .replace(/```[\s\S]*?```/g, ' ')              // blocs de code
    .replace(/`([^`]+)`/g, '$1')                  // code en ligne
    .replace(/\*\*([^*]+)\*\*/g, '$1')            // gras
    .replace(/^#{1,4}\s+/gm, '')                  // titres
    .replace(/^\s*[-*•]\s+/gm, '')                // puces
    .replace(/\b(immo|public)\./g, '')            // préfixes de schéma
    // Noms techniques lus en français (« la vue v_prix… » ne doit pas devenir « la vue la vue… »)
    .replace(/(?:\bla\s+)?(?:\bvue\s+(?:[\p{L}‑-]+\s+)?)?\bv_prix_m2_commune_mat\b/giu, 'la vue matérialisée des prix')
    .replace(/(?:\bla\s+)?(?:\bvue\s+)?\bv_prix_m2_commune\b/gi, 'la vue des prix')
    .replace(/(?:\bla\s+)?(?:\btable\s+)?\bdvf_mutations\b/gi, 'la table des ventes')
    .replace(/(?:\bla\s+)?(?:\btable\s+)?\binsee_communes\b/gi, 'la table des communes')
    .replace(/\bnb_/gi, 'nombre de ')
    .replace(/\bprix_m2_moyen\b/gi, 'prix moyen au mètre carré')
    .replace(/_/g, ' ')                           // autres identifiants : soulignés lus comme des espaces
    .replace(/€\s*\/\s*m²|€\/m2/gi, ' euros par mètre carré')
    .replace(/\bm²|\bm2\b/gi, ' mètre carré')
    .replace(/€/g, ' euros')
    .replace(/%/g, ' pour cent')
    .replace(/≈/g, 'environ ')
    .replace(/→|->/g, ', puis ')
    .replace(/\bSQL\b/g, 'S Q L')
    .replace(/\bDVF\b/g, 'D V F')
    .replace(/\bINSEE\b/g, 'Insee')
    .replace(/\s+/g, ' ')
    .trim()
  if (t.length > maxChars) {
    // Coupe à la fin d'une phrase pour ne pas s'arrêter au milieu d'un mot
    const cut = t.slice(0, maxChars)
    const end = Math.max(cut.lastIndexOf('. '), cut.lastIndexOf(' ; '), cut.lastIndexOf('! '), cut.lastIndexOf('? '))
    t = (end > maxChars * 0.5 ? cut.slice(0, end + 1) : cut) + ' Le détail est affiché à l’écran.'
  }
  return t
}

/** Découpe en phrases de taille raisonnable : certains navigateurs coupent les énoncés trop longs. */
export function splitSentences(text: string, max = 220): string[] {
  const sentences = text.match(/[^.!?;]+[.!?;]?/g) ?? [text]
  const chunks: string[] = []
  let current = ''
  for (const raw of sentences) {
    const s = raw.trim()
    if (!s) continue
    if ((current + ' ' + s).length > max && current) {
      chunks.push(current)
      current = s
    } else current = current ? `${current} ${s}` : s
  }
  if (current) chunks.push(current)
  return chunks
}
