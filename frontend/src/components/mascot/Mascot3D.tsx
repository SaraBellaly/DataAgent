/**
 * Lumi, la mascotte 3D : robote stylisée construite en code (React Three Fiber), sans modèle externe.
 * États : welcome, thinking, processing, success, error ; `speaking` anime la bouche (voix, étape 5).
 */
import { ContactShadows } from '@react-three/drei'
import { Canvas, useFrame } from '@react-three/fiber'
import { useMemo, useRef } from 'react'
import * as THREE from 'three'

import type { AgentMood } from '../../chat/useConversation'

const C = {
  shell: '#fbf8ff',
  shellShade: '#ece6fa',
  joint: '#b9a7ea',
  jointDark: '#8e7cc9',
  skin: '#ffe6df',
  blush: '#f6a8c2',
  hair: '#5d4a8c',
  hairLight: '#7a64ad',
  eye: '#3a2d5f',
  iris: '#7f6ad0',
  mouth: '#c4587f',
  glowPink: '#f39cc0',
  glowLav: '#b79cff',
  mint: '#7fd8b4',
  visor: '#cdb9ff',
}

const damp = THREE.MathUtils.damp

// Position de la souris dans la fenêtre (-1..1), partagée par toutes les instances
const pointer = { x: 0, y: 0 }
if (typeof window !== 'undefined') {
  window.addEventListener('pointermove', (e) => {
    pointer.x = (e.clientX / window.innerWidth) * 2 - 1
    pointer.y = -((e.clientY / window.innerHeight) * 2 - 1)
  })
}

type RobotProps = { mood: AgentMood; speaking: boolean; reduced: boolean }

function Robot({ mood, speaking, reduced }: RobotProps) {
  const root = useRef<THREE.Group>(null)
  const head = useRef<THREE.Group>(null)
  const eyes = useRef<THREE.Group>(null)
  const openEyes = useRef<THREE.Group>(null)
  const happyEyes = useRef<THREE.Group>(null)
  const browL = useRef<THREE.Mesh>(null)
  const browR = useRef<THREE.Mesh>(null)
  const smile = useRef<THREE.Mesh>(null)
  const mouthOpen = useRef<THREE.Mesh>(null)
  const armR = useRef<THREE.Group>(null)
  const torso = useRef<THREE.Group>(null)
  const visorMat = useRef<THREE.MeshPhysicalMaterial>(null)
  const scan = useRef<THREE.Mesh>(null)
  const ringL = useRef<THREE.MeshStandardMaterial>(null)
  const ringR = useRef<THREE.MeshStandardMaterial>(null)
  const chest = useRef<THREE.MeshStandardMaterial>(null)
  const thoughts = useRef<THREE.Group>(null)
  const cubes = useRef<THREE.Group>(null)
  const halo = useRef<THREE.Mesh>(null)  // plan texturé
  const haloMat = useRef<THREE.MeshBasicMaterial>(null)

  const blink = useRef({ next: 2, until: 0 })
  const moodStart = useRef(0)
  const lastMood = useRef<AgentMood>(mood)
  const tmpColor = useMemo(() => new THREE.Color(), [])
  // Halo : dégradé radial blanc -> transparent, teinté par la couleur de l'état
  const haloTexture = useMemo(() => {
    const canvas = document.createElement('canvas')
    canvas.width = canvas.height = 256
    const ctx = canvas.getContext('2d')
    if (ctx) {
      const g = ctx.createRadialGradient(128, 128, 0, 128, 128, 128)
      g.addColorStop(0, 'rgba(255,255,255,1)')
      g.addColorStop(0.45, 'rgba(255,255,255,0.55)')
      g.addColorStop(1, 'rgba(255,255,255,0)')
      ctx.fillStyle = g
      ctx.fillRect(0, 0, 256, 256)
    }
    const texture = new THREE.CanvasTexture(canvas)
    texture.colorSpace = THREE.SRGBColorSpace
    return texture
  }, [])
  const colors = useMemo(
    () => ({
      pink: new THREE.Color(C.glowPink),
      lav: new THREE.Color(C.glowLav),
      mint: new THREE.Color(C.mint),
      rose: new THREE.Color('#f07c9c'),
      visor: new THREE.Color(C.visor),
      visorError: new THREE.Color('#ffb8c9'),
      visorOk: new THREE.Color('#bff0dc'),
    }),
    [],
  )

  useFrame((state, delta) => {
    const t = state.clock.elapsedTime
    const dt = Math.min(delta, 0.05)
    if (lastMood.current !== mood) {
      lastMood.current = mood
      moodStart.current = t
    }
    const since = t - moodStart.current
    const motion = reduced ? 0 : 1

    // ----- Corps : respiration, balancement, petit saut de joie -----
    if (root.current) {
      const hop = mood === 'success' && since < 1.2 ? Math.abs(Math.sin(since * Math.PI * 2.5)) * 0.18 * (1 - since / 1.2) : 0
      root.current.position.y = damp(root.current.position.y, (Math.sin(t * 1.6) * 0.035 + hop) * motion, 8, dt)
      root.current.rotation.z = damp(root.current.rotation.z, Math.sin(t * 0.7) * 0.025 * motion, 4, dt)
    }
    if (torso.current) torso.current.scale.setScalar(1 + Math.sin(t * 1.6) * 0.008 * motion)

    // ----- Tête : suit la souris ; inclinaison selon l'état -----
    if (head.current) {
      let yaw = pointer.x * 0.45
      let pitch = -pointer.y * 0.22
      let roll = 0
      if (mood === 'thinking') {
        yaw = 0.25 + Math.sin(t * 0.8) * 0.08
        pitch = -0.22
        roll = 0.16
      } else if (mood === 'processing') {
        pitch = 0.08
        yaw = Math.sin(t * 1.4) * 0.12
      } else if (mood === 'error') {
        yaw = Math.sin(since * 5) * 0.22 * Math.max(0, 1 - since / 2.2)
        pitch = 0.14
        roll = -0.06
      } else if (mood === 'success') {
        roll = Math.sin(t * 2) * 0.06
        pitch = -0.08
      }
      head.current.rotation.y = damp(head.current.rotation.y, yaw * motion, 5, dt)
      head.current.rotation.x = damp(head.current.rotation.x, pitch * motion, 5, dt)
      head.current.rotation.z = damp(head.current.rotation.z, roll * motion, 5, dt)
    }

    // ----- Yeux : clignements aléatoires, regard, yeux rieurs en cas de succès -----
    const b = blink.current
    if (t > b.next) {
      b.until = t + 0.13
      b.next = t + 2 + Math.random() * 3.5
    }
    const happy = mood === 'success' || (mood === 'welcome' && speaking === false && Math.sin(t * 0.5) > 0.92)
    if (openEyes.current && happyEyes.current) {
      openEyes.current.visible = !happy
      happyEyes.current.visible = happy
      const lid = t < b.until ? 0.1 : mood === 'error' ? 0.72 : 1
      openEyes.current.scale.y = damp(openEyes.current.scale.y, lid, 30, dt)
    }
    if (eyes.current) {
      const lookX = mood === 'thinking' ? 0.05 : pointer.x * 0.04
      const lookY = mood === 'thinking' ? 0.06 : mood === 'error' ? -0.03 : pointer.y * 0.03
      eyes.current.position.x = damp(eyes.current.position.x, lookX * motion, 6, dt)
      eyes.current.position.y = damp(eyes.current.position.y, lookY * motion, 6, dt)
    }
    if (browL.current && browR.current) {
      const raise = mood === 'thinking' ? 0.06 : mood === 'success' ? 0.04 : 0
      const tilt = mood === 'error' ? 0.28 : mood === 'thinking' ? -0.12 : 0
      browL.current.position.y = damp(browL.current.position.y, 0.41 + raise, 6, dt)
      browR.current.position.y = damp(browR.current.position.y, 0.41 + raise * (mood === 'thinking' ? 1.6 : 1), 6, dt)
      browL.current.rotation.z = damp(browL.current.rotation.z, -0.08 - tilt, 6, dt)
      browR.current.rotation.z = damp(browR.current.rotation.z, 0.08 + tilt, 6, dt)
    }

    // ----- Bouche : sourire au repos, ouverture rythmée quand elle parle -----
    if (smile.current && mouthOpen.current) {
      const talk = speaking && !reduced ? 0.35 + 0.65 * Math.abs(Math.sin(t * 13) * Math.sin(t * 7.3 + 1)) : 0
      const open = damp(mouthOpen.current.scale.y, speaking ? Math.max(0.15, talk) : 0.0001, 18, dt)
      mouthOpen.current.scale.y = open
      mouthOpen.current.visible = open > 0.02
      smile.current.visible = open <= 0.02
      smile.current.scale.y = mood === 'error' ? -0.7 : 1
      smile.current.position.y = mood === 'error' ? -0.47 : -0.42
    }

    // ----- Bras droit : salut de bienvenue, bras levé de joie -----
    if (armR.current) {
      let target = 0.12
      if (mood === 'welcome') target = 2.35 + Math.sin(t * 6) * 0.32 * motion
      else if (mood === 'success') target = since < 2 ? 2.6 + Math.sin(t * 8) * 0.15 : 0.12
      else if (mood === 'thinking') target = 1.2
      armR.current.rotation.z = damp(armR.current.rotation.z, target, 5, dt)
    }

    // ----- Lumières : visière, casque, poitrine -----
    const glow = mood === 'success' ? colors.mint : mood === 'error' ? colors.rose : mood === 'processing' ? colors.lav : colors.pink
    const pulse = 0.55 + Math.sin(t * (mood === 'processing' ? 6 : mood === 'thinking' ? 3 : 1.6)) * 0.35
    for (const ring of [ringL.current, ringR.current, chest.current]) {
      if (!ring) continue
      ring.emissive.lerp(glow, 0.08)
      ring.emissiveIntensity = 0.6 + pulse * 0.9
    }
    if (visorMat.current) {
      const target = mood === 'error' ? colors.visorError : mood === 'success' ? colors.visorOk : colors.visor
      visorMat.current.color.lerp(target, 0.06)
      tmpColor.copy(glow)
      visorMat.current.emissive.lerp(tmpColor, 0.05)
      visorMat.current.emissiveIntensity = mood === 'processing' || mood === 'thinking' ? 0.25 + pulse * 0.25 : 0.12
    }
    if (scan.current) {
      scan.current.visible = mood === 'processing' || mood === 'thinking'
      scan.current.rotation.y = Math.sin(t * 3.2) * 0.42
    }

    // ----- Effets : bulles de pensée, cubes de données, halo -----
    if (thoughts.current) {
      thoughts.current.visible = mood === 'thinking'
      thoughts.current.rotation.y = t * 1.4
      thoughts.current.children.forEach((c, i) => (c.position.y = 1.55 + Math.sin(t * 3 + i * 1.3) * 0.08))
    }
    if (cubes.current) {
      cubes.current.visible = mood === 'processing'
      cubes.current.rotation.y = -t * 1.8
      cubes.current.children.forEach((c, i) => {
        c.rotation.x = t * 2 + i
        c.rotation.y = t * 1.5 + i
      })
    }
    if (halo.current && haloMat.current) {
      haloMat.current.color.lerp(glow, 0.08)
      const show = mood === 'success' ? Math.max(0, 1 - since / 2.5) : mood === 'error' ? 0.35 : 0.18
      haloMat.current.opacity = damp(haloMat.current.opacity, show * (0.6 + pulse * 0.4), 6, dt)
      halo.current.scale.setScalar(1 + (mood === 'success' ? since * 0.25 : Math.sin(t * 1.6) * 0.03))
    }
  })

  const shell = <meshPhysicalMaterial color={C.shell} roughness={0.28} clearcoat={0.9} clearcoatRoughness={0.2} />
  const joint = <meshStandardMaterial color={C.joint} roughness={0.4} metalness={0.1} />
  const hair = <meshStandardMaterial color={C.hair} roughness={0.42} />

  return (
    <group ref={root}>
      {/* Halo doux derrière la mascotte (texture en dégradé radial) */}
      <mesh ref={halo} position={[0, -0.55, -1.6]}>
        <planeGeometry args={[5.2, 5.2]} />
        <meshBasicMaterial ref={haloMat} map={haloTexture} color={C.glowPink} transparent opacity={0.18} depthWrite={false} />
      </mesh>

      {/* ---------------- Corps (proportions « chibi » : grosse tête, buste court) ---------------- */}
      <group ref={torso} position={[0, -1.78, 0]}>
        <mesh scale={[1.05, 1, 0.82]}>
          <capsuleGeometry args={[0.56, 0.42, 16, 40]} />
          {shell}
        </mesh>
        {/* Plastron et emblème lumineux */}
        <mesh position={[0, 0.06, 0.4]} scale={[1, 1.05, 0.38]}>
          <sphereGeometry args={[0.3, 40, 40]} />
          <meshPhysicalMaterial color={C.shellShade} roughness={0.3} clearcoat={0.6} />
        </mesh>
        <mesh position={[0, 0.08, 0.52]} rotation={[0, 0, Math.PI / 4]}>
          <torusGeometry args={[0.09, 0.028, 16, 40]} />
          <meshStandardMaterial ref={chest} color="#ffffff" emissive={C.glowPink} emissiveIntensity={1} />
        </mesh>
        {/* Ceinture lavande */}
        <mesh position={[0, -0.36, 0]} rotation={[Math.PI / 2, 0, 0]} scale={[1.05, 0.82, 1]}>
          <torusGeometry args={[0.55, 0.055, 16, 56]} />
          {joint}
        </mesh>
        {/* Col */}
        <mesh position={[0, 0.5, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.27, 0.06, 16, 40]} />
          {joint}
        </mesh>
      </group>

      {/* Épaules */}
      {[-1, 1].map((side) => (
        <mesh key={side} position={[0.7 * side, -1.38, 0]} scale={[1, 0.9, 0.95]}>
          <sphereGeometry args={[0.22, 32, 32]} />
          {joint}
        </mesh>
      ))}
      {/* Bras gauche, le long du corps */}
      <group position={[-0.74, -1.4, 0]} rotation={[0, 0, -0.16]}>
        <mesh position={[0, -0.38, 0]}>
          <capsuleGeometry args={[0.16, 0.38, 12, 24]} />
          {shell}
        </mesh>
        <mesh position={[0, -0.8, 0.02]}>
          <sphereGeometry args={[0.19, 32, 32]} />
          {shell}
        </mesh>
      </group>
      {/* Bras droit : il salue */}
      <group ref={armR} position={[0.74, -1.4, 0]} rotation={[0, 0, 0.12]}>
        <mesh position={[0, -0.38, 0]}>
          <capsuleGeometry args={[0.16, 0.38, 12, 24]} />
          {shell}
        </mesh>
        <mesh position={[0, -0.8, 0.02]}>
          <sphereGeometry args={[0.2, 32, 32]} />
          {shell}
        </mesh>
        <mesh position={[0, -0.83, 0.2]}>
          <circleGeometry args={[0.075, 32]} />
          <meshBasicMaterial color={C.glowPink} />
        </mesh>
      </group>

      {/* Cou */}
      <mesh position={[0, -1.08, 0]}>
        <cylinderGeometry args={[0.17, 0.2, 0.22, 32]} />
        <meshStandardMaterial color={C.jointDark} roughness={0.45} />
      </mesh>

      {/* ---------------- Tête ---------------- */}
      <group ref={head} position={[0, -0.05, 0]}>
        {/* Visage */}
        <mesh scale={[1, 0.97, 0.93]}>
          <sphereGeometry args={[0.95, 96, 96]} />
          <meshStandardMaterial color={C.skin} emissive="#ffd6cc" emissiveIntensity={0.16} roughness={0.6} />
        </mesh>

        {/* Cheveux : calotte inclinée vers l'arrière (front dégagé) */}
        <mesh rotation={[-0.72, 0, 0]} scale={[1.05, 1.03, 1.04]}>
          <sphereGeometry args={[0.97, 96, 96, 0, Math.PI * 2, 0, Math.PI * 0.56]} />
          {hair}
        </mesh>
        {/* Frange balayée sur le côté */}
        <mesh position={[0.16, 0.6, 0.6]} rotation={[1.08, -0.18, -0.34]} scale={[0.74, 0.16, 0.36]}>
          <sphereGeometry args={[1, 48, 48]} />
          {hair}
        </mesh>
        <mesh position={[-0.6, 0.38, 0.5]} rotation={[0.35, 0.55, 1.05]} scale={[0.32, 0.14, 0.28]}>
          <sphereGeometry args={[1, 32, 32]} />
          {hair}
        </mesh>
        {/* Reflet brillant sur les cheveux */}
        <mesh position={[0.18, 0.72, 0.5]} rotation={[1.1, -0.18, -0.34]} scale={[0.4, 0.04, 0.12]}>
          <sphereGeometry args={[1, 24, 24]} />
          <meshStandardMaterial color={C.hairLight} emissive={C.hairLight} emissiveIntensity={0.35} roughness={0.3} />
        </mesh>
        {/* Carré court : côtés et arrière */}
        {[-1, 1].map((side) => (
          <mesh key={side} position={[0.74 * side, -0.28, -0.05]} rotation={[0.08, 0, -0.1 * side]} scale={[0.24, 0.72, 0.6]}>
            <sphereGeometry args={[1, 40, 40]} />
            {hair}
          </mesh>
        ))}
        <mesh position={[0, -0.22, -0.52]} scale={[0.9, 0.8, 0.55]}>
          <sphereGeometry args={[1, 40, 40]} />
          {hair}
        </mesh>

        {/* Sourcils */}
        <mesh ref={browL} position={[-0.33, 0.41, 0.86]} rotation={[0, 0, -0.08]}>
          <capsuleGeometry args={[0.024, 0.15, 6, 12]} />
          <meshStandardMaterial color={C.hair} />
        </mesh>
        <mesh ref={browR} position={[0.33, 0.41, 0.86]} rotation={[0, 0, 0.08]}>
          <capsuleGeometry args={[0.024, 0.15, 6, 12]} />
          <meshStandardMaterial color={C.hair} />
        </mesh>

        {/* Yeux (ouverts / rieurs) */}
        <group ref={eyes}>
          <group ref={openEyes}>
            {[-1, 1].map((side) => (
              <group key={side} position={[0.33 * side, 0.05, 0.8]}>
                <mesh scale={[1, 1.25, 0.55]}>
                  <sphereGeometry args={[0.165, 40, 40]} />
                  <meshPhysicalMaterial color={C.eye} roughness={0.15} clearcoat={1} />
                </mesh>
                <mesh position={[0, -0.045, 0.075]} scale={[1, 1.1, 0.3]}>
                  <sphereGeometry args={[0.105, 32, 32]} />
                  <meshStandardMaterial color={C.iris} emissive={C.iris} emissiveIntensity={0.45} />
                </mesh>
                <mesh position={[0.055 * side, 0.075, 0.105]}>
                  <sphereGeometry args={[0.048, 20, 20]} />
                  <meshBasicMaterial color="#ffffff" />
                </mesh>
                <mesh position={[-0.045 * side, -0.075, 0.105]}>
                  <sphereGeometry args={[0.022, 12, 12]} />
                  <meshBasicMaterial color="#ffffff" />
                </mesh>
              </group>
            ))}
          </group>
          <group ref={happyEyes} visible={false}>
            {[-1, 1].map((side) => (
              <mesh key={side} position={[0.33 * side, 0.03, 0.86]}>
                <torusGeometry args={[0.1, 0.03, 12, 28, Math.PI]} />
                <meshStandardMaterial color={C.eye} />
              </mesh>
            ))}
          </group>
        </group>

        {/* Joues */}
        {[-1, 1].map((side) => (
          <mesh key={side} position={[0.55 * side, -0.25, 0.72]} rotation={[0, 0.55 * side, 0]}>
            <circleGeometry args={[0.12, 32]} />
            <meshBasicMaterial color={C.blush} transparent opacity={0.6} depthWrite={false} />
          </mesh>
        ))}

        {/* Bouche */}
        <mesh ref={smile} position={[0, -0.42, 0.84]} rotation={[0, 0, Math.PI]}>
          <torusGeometry args={[0.1, 0.024, 12, 28, Math.PI]} />
          <meshStandardMaterial color={C.mouth} />
        </mesh>
        <mesh ref={mouthOpen} position={[0, -0.43, 0.82]} scale={[1, 0.0001, 0.5]}>
          <sphereGeometry args={[0.1, 24, 24]} />
          <meshStandardMaterial color={C.mouth} />
        </mesh>

        {/* Visière translucide devant les yeux, avec un liseré lumineux */}
        <mesh scale={[1, 0.97, 0.93]}>
          <sphereGeometry args={[1.0, 96, 24, Math.PI / 2 - 0.66, 1.32, Math.PI * 0.38, Math.PI * 0.18]} />
          <meshPhysicalMaterial
            ref={visorMat}
            color={C.visor}
            emissive={C.glowPink}
            emissiveIntensity={0.12}
            transparent
            opacity={0.42}
            roughness={0.04}
            clearcoat={1}
            side={THREE.DoubleSide}
            depthWrite={false}
          />
        </mesh>
        {[Math.PI * 0.38, Math.PI * 0.56].map((theta) => (
          <mesh key={theta} scale={[1, 0.97, 0.93]}>
            <sphereGeometry args={[1.006, 96, 2, Math.PI / 2 - 0.66, 1.32, theta - 0.008, 0.016]} />
            <meshBasicMaterial color="#ffffff" transparent opacity={0.85} side={THREE.DoubleSide} />
          </mesh>
        ))}
        {/* Balayage lumineux de la visière (réflexion, préparation) */}
        <mesh ref={scan} scale={[1, 0.97, 0.93]} visible={false}>
          <sphereGeometry args={[1.012, 32, 8, Math.PI / 2 - 0.06, 0.12, Math.PI * 0.38, Math.PI * 0.18]} />
          <meshBasicMaterial color="#ffffff" transparent opacity={0.65} depthWrite={false} side={THREE.DoubleSide} />
        </mesh>

        {/* Casque audio : arceau et écouteurs aux anneaux lumineux */}
        <mesh position={[0, 0.02, -0.06]}>
          <torusGeometry args={[1.08, 0.065, 16, 80, Math.PI]} />
          {shell}
        </mesh>
        {[-1, 1].map((side) => (
          <group key={side} position={[1.0 * side, -0.02, -0.02]} rotation={[0, 0, (Math.PI / 2) * side]}>
            <mesh>
              <cylinderGeometry args={[0.34, 0.34, 0.26, 48]} />
              {shell}
            </mesh>
            <mesh position={[0, 0.135 * side, 0]} rotation={[Math.PI / 2, 0, 0]}>
              <torusGeometry args={[0.23, 0.04, 16, 48]} />
              <meshStandardMaterial ref={side < 0 ? ringL : ringR} color="#ffffff" emissive={C.glowPink} emissiveIntensity={1} />
            </mesh>
            <mesh position={[0, 0.13 * side, 0]} rotation={[Math.PI / 2, 0, 0]}>
              <circleGeometry args={[0.19, 40]} />
              <meshStandardMaterial color={C.shellShade} side={THREE.DoubleSide} />
            </mesh>
          </group>
        ))}
      </group>

      {/* Bulles de pensée */}
      <group ref={thoughts} visible={false}>
        {[0, 1, 2].map((i) => (
          <mesh key={i} position={[Math.cos((i / 3) * Math.PI * 2) * 0.9, 1.45, Math.sin((i / 3) * Math.PI * 2) * 0.9]}>
            <sphereGeometry args={[0.07 + i * 0.025, 20, 20]} />
            <meshStandardMaterial color="#ffffff" emissive={C.glowLav} emissiveIntensity={0.8} />
          </mesh>
        ))}
      </group>

      {/* Cubes de données */}
      <group ref={cubes} visible={false} position={[0, -0.3, 0]}>
        {[0, 1, 2, 3].map((i) => (
          <mesh key={i} position={[Math.cos((i / 4) * Math.PI * 2) * 1.55, (i % 2) * 0.4 - 0.2, Math.sin((i / 4) * Math.PI * 2) * 1.55]}>
            <boxGeometry args={[0.16, 0.16, 0.16]} />
            <meshStandardMaterial color="#ffffff" emissive={i % 2 ? C.glowPink : C.glowLav} emissiveIntensity={0.9} />
          </mesh>
        ))}
      </group>
    </group>
  )
}

/** Cadrage : `full` (tête et buste, accueil) ou `bust` (tête, en-tête de conversation). */
export default function Mascot3D({
  mood,
  speaking = false,
  framing = 'full',
  reduced: reducedSetting = false,
}: {
  mood: AgentMood
  speaking?: boolean
  framing?: 'full' | 'bust'
  /** Réglage « limiter les animations » de l'application */
  reduced?: boolean
}) {
  const systemReduced = useRef(
    typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches,
  ).current
  const reduced = Boolean(systemReduced || reducedSetting)
  const camera = framing === 'full' ? { position: [0, -0.7, 9.4] as const, fov: 30 } : { position: [0, -0.1, 4.7] as const, fov: 30 }

  return (
    <Canvas
      dpr={[1, 2]}
      camera={{ position: [...camera.position], fov: camera.fov }}
      gl={{ antialias: true, alpha: true, powerPreference: 'low-power' }}
      onCreated={({ camera: cam }) => {
        cam.lookAt(0, framing === 'full' ? -0.72 : -0.1, 0)
      }}
      style={{ background: 'transparent' }}
    >
      <ambientLight intensity={0.85} />
      <hemisphereLight args={['#fff4fa', '#e6dcff', 0.7]} />
      <directionalLight position={[3, 4, 5]} intensity={1.6} color="#ffffff" />
      <directionalLight position={[-4, 1, -2]} intensity={0.9} color="#f7c4dc" />
      <pointLight position={[0, 1, 3]} intensity={0.6} color="#d8c8ff" />
      <Robot mood={mood} speaking={speaking} reduced={reduced} />
      {framing === 'full' && <ContactShadows position={[0, -2.62, 0]} opacity={0.28} scale={6} blur={2.6} far={3} color="#8c71d8" />}
    </Canvas>
  )
}
