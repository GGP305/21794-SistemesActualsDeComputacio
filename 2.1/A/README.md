# Histograma con Intel TBB

Este proyecto implementa un sistema de generación de histogramas utilizando paralelización con **Intel Threading Building Blocks (TBB)**. El programa compara el rendimiento entre una implementación secuencial y una paralela utilizando las primitivas de TBB.

## Descripción

El programa genera un conjunto de números aleatorios siguiendo una distribución exponencial y construye un histograma dividiéndolos en rangos. Implementa el patrón **Map-Reduce-Scan** en dos versiones:

- **Versión Secuencial**: Procesamiento lineal de los datos
- **Versión Paralela (TBB)**: Utiliza `parallel_for`, `parallel_reduce` y `parallel_scan`

## Características

### Fases del Procesamiento

1. **Mapeo**: Asigna cada número a su rango correspondiente
2. **Reducción**: Cuenta los elementos en cada rango
3. **Escaneo**: Calcula el histograma acumulado

### Configuración

- **Número de rangos**: 4 (configurable mediante `CANTIDAD_RANGOS`)
- **Cantidad de elementos**: 10 (ajustable en `main()`)
- **Valor máximo**: 120 (ajustable en `main()`)
- **Distribución**: Exponencial con λ = 0.05
- **Modo DEBUG**: Muestra información detallada de cada fase

## Requisitos

- **Compilador C++**: Compatible con C++17 o superior
- **Intel TBB**: Threading Building Blocks instalado en el sistema

## Compilación

```bash
g++ -std=c++17 -O3 main.cpp -ltbb -o histograma
```

## Ejecución

```bash
./histograma
```

## Salida del Programa

El programa muestra:

1. **Configuración de rangos**: Límites de cada rango
2. **Datos de entrada**: Vector de números generados (en modo DEBUG)
3. **Ejecución paralela (TBB)**:
   - Fase 1: Mapeo
   - Fase 2: Reducción
   - Fase 3: Escaneo
   - Resultado: Histograma acumulado
   - Tiempo de ejecución
4. **Ejecución secuencial**:
   - Mismas fases y resultado
   - Tiempo de ejecución

### Ejemplo de Salida

```
========================================
   CONFIGURACION DE RANGOS
========================================
Numero de rangos: 4

  Rango 1: [0 - 30]
  Rango 2: [31 - 60]
  Rango 3: [61 - 90]
  Rango 4: [91 - 120]

Datos de entrada: { 2, 5, 8, 15, 23, 45, 67, 89, 102, 115 }

========================================
   EJECUCION PARALELA (TBB)
========================================
>>> Fase 1 - Mapeo:
...
Resultado: [ 5; 6; 8; 10; ]
Tiempo transcurrido: 0.00234 seg
========================================
```

## Primitivas TBB Utilizadas

### parallel_for
Paraleliza el mapeo de elementos a rangos, dividiendo el trabajo en bloques (`blocked_range`).

### parallel_reduce
Realiza la reducción paralela para contar elementos por rango, combinando resultados parciales.

### parallel_scan
Implementa el escaneo acumulativo en paralelo para obtener el histograma final.

## Modo DEBUG

Para activar/desactivar el modo debug, modifica la línea:

```cpp
#define DEBUG 1  // 1 para activar, 0 para desactivar
```

## Personalización

### Cambiar el número de rangos

```cpp
const int CANTIDAD_RANGOS = 4;  // Modificar según necesidad
```

### Ajustar parámetros de generación

En la función `main()`:

```cpp
const int CANTIDAD_ELEMENTOS = 10;    // Número de elementos
const int VALOR_MAXIMO = 120;         // Valor máximo posible
```

### Modificar la distribución

En `generarNumerosAleatorios()`:

```cpp
std::exponential_distribution<> distribucion(0.05);  // Cambiar lambda
```

## Estructura del Código

- **Funciones auxiliares**: Generación de números, impresión, cálculo de índices
- **Solución secuencial**: `ejecutarSecuencial()`
- **Solución paralela**: `ejecutarParalelo()`
- **Función principal**: `main()` - Coordina la ejecución y medición de tiempos

## Notas

- Los datos se generan con distribución exponencial para simular escenarios reales
- Los números se ordenan antes del procesamiento para facilitar la depuración
- El tiempo de ejecución se mide con `tbb::tick_count` para mayor precisión
- La comparación de tiempos permite evaluar el beneficio de la paralelización