import { motion } from "framer-motion";
import { ReactNode } from "react";

type Props = {
  children:   ReactNode;
  delay?:     number;
  className?: string;
};

/**
 * ScrollReveal — viewport-triggered fade + scale spring.
 * once:false so elements re-animate on scroll back up.
 */
export default function ScrollReveal({ children, delay = 0, className = "" }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.96, y: 20 }}
      whileInView={{ opacity: 1, scale: 1, y: 0 }}
      viewport={{ once: false, amount: 0.15 }}
      transition={{ type: "spring", stiffness: 120, damping: 22, mass: 0.6, delay }}
      className={className}
    >
      {children}
    </motion.div>
  );
}
