package com.greenci;

public class App {
    public static void main(String[] args) throws InterruptedException {
        System.out.println("GreenCI Resource Monitor Starting...");

        for (int i = 0; i < 10; i++) {  // 10 measurements, one per second
            long totalMemory = Runtime.getRuntime().totalMemory();
            long freeMemory = Runtime.getRuntime().freeMemory();
            long usedMemory = totalMemory - freeMemory;

            int cores = Runtime.getRuntime().availableProcessors();

            System.out.println("Measurement " + (i + 1));
            System.out.println("Total Memory: " + totalMemory + " bytes");
            System.out.println("Free Memory: " + freeMemory + " bytes");
            System.out.println("Used Memory: " + usedMemory + " bytes");
            System.out.println("Available processors (cores): " + cores);
            System.out.println("-----------------------------");

            Thread.sleep(1000);  // Wait 1 second between each check
        }

        System.out.println("Resource monitoring complete.");
    }
}
