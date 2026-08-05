# Especificación del paquete de evidencia

## Contenido mínimo

- locks;
- geometría;
- especies;
- pseudopotenciales;
- FDF;
- runtime;
- DAG materializado;
- tareas;
- datos crudos;
- regresiones;
- matrices;
- inversas;
- residuos;
- gates;
- sensibilidad;
- fallos y trazas;
- decisión humana si existe;
- manifiesto completo;
- salida del verificador.

## Portabilidad

El paquete debe poder verificarse sin acceder al clúster original. No necesita contener el binario
si la política lo prohíbe, pero sí su hash y evidencia de identidad.


## Convenciones normativas

Las palabras **DEBE**, **NO DEBE**, **DEBERÍA**, **NO DEBERÍA** y **PUEDE** son normativas.  
Una regla marcada como DEBE es obligatoria para conformidad. Una regla marcada como DEBERÍA
puede omitirse sólo con una justificación registrada y auditable.
