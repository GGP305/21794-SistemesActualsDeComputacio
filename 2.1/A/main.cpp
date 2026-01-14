#include <iostream>
#include <vector>
#include <array>
#include <cmath>
#include <random>
#include <algorithm>
#include <tbb/tbb.h>
#include <oneapi/tbb/info.h>
#include <oneapi/tbb/parallel_for.h>
#include <oneapi/tbb/parallel_reduce.h>
#include <oneapi/tbb/parallel_scan.h>
#include <oneapi/tbb/parallel_invoke.h>

// Config
#define DEBUG 1
const int CANTIDAD_RANGOS = 4;

// ============================================================================
// FUNCIONES AUXILIARES
// ============================================================================

/*
 * Genera un vector con numeros aleatorios siguiendo una distribucion exponencial
 */
std::vector<int> generarNumerosAleatorios(int cantidad, int valorMaximo)
{
    std::mt19937 generador(std::random_device{}());
    std::exponential_distribution<> distribucion(0.05);
    
    std::vector<int> resultado(cantidad);
    for (auto& elemento : resultado)
    {
        elemento = std::min(valorMaximo, static_cast<int>(distribucion(generador)));
    }
    
    return resultado;
}

/*
 * Imprime un array de enteros con formato
 */
void imprimirArray(const std::array<int, CANTIDAD_RANGOS>& arr)
{
    std::cout << "[ ";
    for (int val : arr)
    {
        std::cout << val << "; ";
    }
    std::cout << "]";
}

/*
 * Calcula el indice del rango correspondiente a un valor
 */
int calcularIndiceRango(int valor, int tamanoRango)
{
    int valorAjustado = (valor > 0) ? (valor - 1) : valor;
    return std::min(valorAjustado / tamanoRango, CANTIDAD_RANGOS - 1);
}

// ============================================================================
// SOLUCION SECUENCIAL
// ============================================================================

void ejecutarSecuencial(const std::vector<int>& datos, int tamanoRango)
{
    int totalElementos = datos.size();
    
    // --- PASO 1: Mapeo ---
    std::vector<std::array<int, CANTIDAD_RANGOS>> valoresMapeados(totalElementos);
    
    for (int i = 0; i < totalElementos; ++i)
    {
        int indice = calcularIndiceRango(datos[i], tamanoRango);
        std::array<int, CANTIDAD_RANGOS> temp{};
        temp[indice] = 1;
        valoresMapeados[i] = temp;
    }
    
#if DEBUG
    std::cout << ">>> Fase 1 - Mapeo:" << std::endl;
    for (size_t i = 0; i < valoresMapeados.size(); ++i)
    {
        imprimirArray(valoresMapeados[i]);
        if (i < valoresMapeados.size() - 1) std::cout << "\n";
    }
    std::cout << std::endl;
#endif

    // --- PASO 2: Reduccion ---
    std::array<int, CANTIDAD_RANGOS> histograma{};
    
    for (const auto& mapeado : valoresMapeados)
    {
        for (int j = 0; j < CANTIDAD_RANGOS; ++j)
        {
            histograma[j] += mapeado[j];
        }
    }
    
#if DEBUG
    std::cout << std::endl << ">>> Fase 2 - Reduccion:" << std::endl;
    imprimirArray(histograma);
    std::cout << std::endl;
#endif

    // --- PASO 3: Escaneo acumulativo ---
    std::array<int, CANTIDAD_RANGOS> histogramaAcumulado{};
    int acumulador = 0;
    
    for (int i = 0; i < CANTIDAD_RANGOS; ++i)
    {
        acumulador += histograma[i];
        histogramaAcumulado[i] = acumulador;
    }
    
#if DEBUG
    std::cout << std::endl << ">>> Fase 3 - Escaneo:" << std::endl;
#endif
    
    std::cout << "Resultado: ";
    imprimirArray(histogramaAcumulado);
    std::cout << std::endl << std::endl;
}

// ============================================================================
// SOLUCION PARALELA CON TBB
// ============================================================================

void ejecutarParalelo(std::vector<int>& datos, int tamanoRango)
{
    int totalElementos = datos.size();
    
    // --- PASO 1: Mapeo en paralelo ---
    std::vector<std::array<int, CANTIDAD_RANGOS>> valoresMapeados(totalElementos);
    
    tbb::parallel_for(
        tbb::blocked_range<int>(0, totalElementos),
        [&](const tbb::blocked_range<int>& rango)
        {
            for (int i = rango.begin(); i < rango.end(); ++i)
            {
                int indice = calcularIndiceRango(datos[i], tamanoRango);
                std::array<int, CANTIDAD_RANGOS> temp{};
                temp[indice] = 1;
                valoresMapeados[i] = temp;
            }
        }
    );
    
#if DEBUG
    std::cout << ">>> Fase 1 - Mapeo:" << std::endl;
    for (size_t i = 0; i < valoresMapeados.size(); ++i)
    {
        imprimirArray(valoresMapeados[i]);
        if (i < valoresMapeados.size() - 1) std::cout << "\n";
    }
    std::cout << std::endl;
#endif

    // --- PASO 2: Reduccion en paralelo ---
    auto histograma = tbb::parallel_reduce(
        tbb::blocked_range<int>(0, totalElementos),
        std::array<int, CANTIDAD_RANGOS>{},
        
        // Funcion de reduccion parcial
        [&](const tbb::blocked_range<int>& rango, std::array<int, CANTIDAD_RANGOS> parcial)
        {
            for (int i = rango.begin(); i < rango.end(); ++i)
            {
                for (int j = 0; j < CANTIDAD_RANGOS; ++j)
                {
                    parcial[j] += valoresMapeados[i][j];
                }
            }
            return parcial;
        },
        
        // Funcion de combinacion
        [](std::array<int, CANTIDAD_RANGOS> a, std::array<int, CANTIDAD_RANGOS> b)
        {
            std::array<int, CANTIDAD_RANGOS> combinado{};
            for (int i = 0; i < CANTIDAD_RANGOS; ++i)
            {
                combinado[i] = a[i] + b[i];
            }
            return combinado;
        }
    );
    
#if DEBUG
    std::cout << std::endl << ">>> Fase 2 - Reduccion:" << std::endl;
    imprimirArray(histograma);
    std::cout << std::endl;
#endif

    // --- PASO 3: Escaneo en paralelo ---
    std::array<int, CANTIDAD_RANGOS> histogramaAcumulado{};
    
    tbb::parallel_scan(
        tbb::blocked_range<int>(0, CANTIDAD_RANGOS),
        0,
        [&](const tbb::blocked_range<int>& rango, int suma, bool esFinal)
        {
            for (int i = rango.begin(); i < rango.end(); ++i)
            {
                suma += histograma[i];
                if (esFinal)
                {
                    histogramaAcumulado[i] = suma;
                }
            }
            return suma;
        },
        [](int x, int y) { return x + y; }
    );
    
#if DEBUG
    std::cout << std::endl << ">>> Fase 3 - Escaneo:" << std::endl;
#endif
    
    std::cout << "Resultado: ";
    imprimirArray(histogramaAcumulado);
    std::cout << std::endl << std::endl;
}

// ============================================================================
// FUNCION PRINCIPAL
// ============================================================================

void mostrarConfiguracion(int valorMaximo, int tamanoRango)
{
    std::cout << "========================================" << std::endl;
    std::cout << "   CONFIGURACION DE RANGOS" << std::endl;
    std::cout << "========================================" << std::endl;
    std::cout << "Numero de rangos: " << CANTIDAD_RANGOS << std::endl << std::endl;
    
    for (int i = 0; i < CANTIDAD_RANGOS; ++i)
    {
        int limiteInferior = (i == 0) ? 0 : (valorMaximo - (CANTIDAD_RANGOS - i) * tamanoRango + 1);
        int limiteSuperior = valorMaximo - (CANTIDAD_RANGOS - 1 - i) * tamanoRango;
        
        std::cout << "  Rango " << (i + 1) << ": [" 
                  << limiteInferior << " - " << limiteSuperior << "]" << std::endl;
    }
    std::cout << std::endl;
}

void mostrarVector(const std::vector<int>& vec)
{
    std::cout << "Datos de entrada: { ";
    for (size_t i = 0; i < vec.size(); ++i)
    {
        std::cout << vec[i];
        if (i < vec.size() - 1) std::cout << ", ";
    }
    std::cout << " }" << std::endl << std::endl;
}

int main()
{
    // Parametros del programa
    const int CANTIDAD_ELEMENTOS = 10;
    const int VALOR_MAXIMO = 120;
    const int TAMANO_RANGO = std::ceil(static_cast<double>(VALOR_MAXIMO) / CANTIDAD_RANGOS);
    
    // Generar y ordenar datos
    std::vector<int> datos = generarNumerosAleatorios(CANTIDAD_ELEMENTOS, VALOR_MAXIMO);
    std::sort(datos.begin(), datos.end());
    
    // Mostrar informacion inicial
    std::cout << std::endl;
    mostrarConfiguracion(VALOR_MAXIMO, TAMANO_RANGO);
    
#if DEBUG
    mostrarVector(datos);
#endif

    // Ejecutar version paralela
    std::cout << "========================================" << std::endl;
    std::cout << "   EJECUCION PARALELA (TBB)" << std::endl;
    std::cout << "========================================" << std::endl;
    
    auto inicioParalelo = tbb::tick_count::now();
    ejecutarParalelo(datos, TAMANO_RANGO);
    auto tiempoParalelo = (tbb::tick_count::now() - inicioParalelo).seconds();
    
    std::cout << "Tiempo transcurrido: " << tiempoParalelo << " seg" << std::endl;
    std::cout << "========================================" << std::endl << std::endl;

    // Ejecutar version secuencial
    std::cout << "========================================" << std::endl;
    std::cout << "   EJECUCION SECUENCIAL" << std::endl;
    std::cout << "========================================" << std::endl;
    
    auto inicioSecuencial = tbb::tick_count::now();
    ejecutarSecuencial(datos, TAMANO_RANGO);
    auto tiempoSecuencial = (tbb::tick_count::now() - inicioSecuencial).seconds();
    
    std::cout << "Tiempo transcurrido: " << tiempoSecuencial << " seg" << std::endl;
    std::cout << "========================================" << std::endl << std::endl;

    return 0;
}