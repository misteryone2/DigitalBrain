
import { useEffect, useRef } from "react";
import * as THREE from "three";

function Brain() {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;

    if (!container) {
      return;
    }

    const scene = new THREE.Scene();

    const camera = new THREE.PerspectiveCamera(
      45,
      1,
      0.1,
      100
    );

    camera.position.z = 5;

    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
    });

    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(
      container.clientWidth,
      container.clientHeight
    );

    container.appendChild(renderer.domElement);

    const geometry = new THREE.IcosahedronGeometry(1.25, 2);

    const material = new THREE.MeshStandardMaterial({
      color: 0x3478c8,
      emissive: 0x102c50,
      roughness: 0.4,
      metalness: 0.5,
      wireframe: true,
    });

    const brainMesh = new THREE.Mesh(geometry, material);
    scene.add(brainMesh);

    const light = new THREE.PointLight(0x5ba9ff, 35);
    light.position.set(3, 3, 4);
    scene.add(light);

    scene.add(new THREE.AmbientLight(0xffffff, 1.5));

    const resizeObserver = new ResizeObserver(() => {
      const width = container.clientWidth;
      const height = container.clientHeight;

      if (width === 0 || height === 0) {
        return;
      }

      camera.aspect = width / height;
      camera.updateProjectionMatrix();

      renderer.setSize(width, height);
    });

    resizeObserver.observe(container);

    let animationFrame = 0;

    const animate = () => {
      animationFrame = requestAnimationFrame(animate);

      brainMesh.rotation.y += 0.003;
      brainMesh.rotation.x += 0.001;

      renderer.render(scene, camera);
    };

    animate();

    return () => {
      cancelAnimationFrame(animationFrame);
      resizeObserver.disconnect();
      geometry.dispose();
      material.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, []);

  return <div ref={containerRef} className="brain-container" />;
}

export default Brain;
