package edu.penn.rtg.experiment.tasksetgenerator;

import java.util.Vector;

public class CPU {
	private Vector<VCPU> vcpus;
	private double used_capacity;
	private int hasDoms[];
	
	public CPU(){
		this.vcpus = new Vector<VCPU>();
		this.hasDoms = new int[4];
	}
	
	public boolean hasDomiOnIt(int i){
		if(hasDoms[i] > 0){
			return true;
		}else{
			return false;
		}
	}

	public void setDomiOnIt(int i){
		hasDoms[i] = 1; //dom i run on this core
	}
	
	
	public Vector<VCPU> getVcpus() {
		return vcpus;
	}

	public void setVcpus(Vector<VCPU> vcpus) {
		this.vcpus = vcpus;
	}

	public double getUsed_capacity() {
		return used_capacity;
	}

	public void setUsed_capacity(double used_capacity) {
		this.used_capacity = used_capacity;
	}

	public int[] getHasDoms() {
		return hasDoms;
	}

	public void setHasDoms(int[] hasDoms) {
		this.hasDoms = hasDoms;
	}
	
	
}
