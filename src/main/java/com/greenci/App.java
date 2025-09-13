package com.greenci;

import java.io.FileWriter;
import java.io.IOException;

public class App {
    public static void main(String[] args) throws InterruptedException, IOException {
        System.out.println("GreenCI Resource Monitor Starting...");
        FileWriter writer = new FileWriter("resource_log.csv");
        writer.write("Interval,UsedMemory(bytes),TotalMemory(bytes),FreeMemory(bytes),CPUCores,EnergyEstimate(Wh)\n");
        
        double cpuWattPerCore = 10.0; // Typical estimate: adjust for your hardware
        int cores = Runtime.getRuntime().availableProcessors();

        for (int i = 1; i <= 10; i++) {  // 10 intervals, 1 per second
            long totalMemory = Runtime.getRuntime().totalMemory();
            long freeMemory = Runtime.getRuntime().freeMemory();
            long usedMemory = totalMemory - freeMemory;

            // Estimate energy usage for this 1-second interval
            double energyForInterval = (cpuWattPerCore * cores) * (1.0 / 3600); // watt-hours

            // Print to terminal
            System.out.println("Measurement " + i);
            System.out.println("Total Memory: " + totalMemory + " bytes");
            System.out.println("Free Memory: " + freeMemory + " bytes");
            System.out.println("Used Memory: " + usedMemory + " bytes");
            System.out.println("Available CPU cores: " + cores);
            System.out.printf("Estimated Energy Usage: %.5f Wh%n", energyForInterval);
            System.out.println("-----------------------------");

            // Log to file
            writer.write(i + "," + usedMemory + "," + totalMemory + "," + freeMemory + "," + cores + "," + energyForInterval + "\n");

            Thread.sleep(1000);  // wait 1 sec
        }
        writer.close();
        System.out.println("Resource monitoring complete. Data saved as resource_log.csv");
    }
}
