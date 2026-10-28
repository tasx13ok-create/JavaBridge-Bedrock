package net.fabricmc.api;
/** Type marker only; JavaBridge does not execute Java dedicated-server entrypoints. */
public interface DedicatedServerModInitializer { void onInitializeServer(); }
