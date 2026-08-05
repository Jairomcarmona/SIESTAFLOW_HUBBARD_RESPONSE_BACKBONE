# Directiva para Codex o Antigravity

Implemente el sistema siguiendo los documentos normativos de este paquete.

Prioridades:

1. No hardcodear materiales, geometrías ni cardinalidades.
2. Implementar primero el backend sintético.
3. Mantener dominio, backend, ejecución y evidencia separados.
4. Tratar BARE como contrato no resuelto para SIESTA hasta validación.
5. Rechazar matrices rectangulares.
6. Recomputar gates y U desde datos.
7. Mantener `recommended_single_U_ev = null`.
8. Añadir una matriz requisito -> implementación -> prueba.
9. No declarar equivalencia con `hp.x`.
10. No ejecutar campañas científicas reales en la primera fase.

La implementación debe fallar de forma explícita ante cualquier decisión científica no
materializada en un lock.
