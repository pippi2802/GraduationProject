package edu.penn.rtg.common;

public class GlobalVariable {
	public static final boolean hasGUI = false;
	
	public static final double TIME_PRECISION = 1; 
	public static final long MAX_INTEGER = 2047483647; //9223372036854775807;//largest number of long type in java. 32 bit
	public static final long MAX_NUMBER = 2047483647; //2 * 10^10
	public static final long MIN_INTEGER = 0;
	public static final double MAX_DOUBLE = Math.pow(10, 16);
	public static final double MIN_DOUBLE = Math.pow(0.1, 6);
	public static final double ONE_TIME_UNIT = Math.pow(0.1,6);
	
	//for unicore interface
	public static final double BANDWIDTH_THRESHOLD_UNSCHED = 1.1; //Do not calculate the interface anymore when bw > BANDWIDTH_THRESHOLD;
														//because the bandwidth value only mean the taskset is unschedulable without other meanings.
	public static final double BANDWIDTH_VALUE_UNSCHED = BANDWIDTH_THRESHOLD_UNSCHED + 1; // assign this value as the interface bandwidth for the  unsched taskset 
	public static final boolean FAST_PATH = true;
	
	public static final int TASK_CENTRIC = 1;
	public static final int TASK_CENTRIC_BJORN = 2;
	public static final int MODEL_CENTRIC = 3;
	public static final int HYBRID = 4; 
	public static final int TASK_CENTRIC_UB = 5; 
	
	public static final int MPR_SBF_ARVIND = 101;
	public static final int MPR_SBF_MENG = 102;
	
	
	//whichSchedTest
	public static final int ARVIND_SCHEDTEST = 1;
	public static final int BERTOGNA_SCHEDTEST = 2;
	public static final int ARVIND_SCHEDTEST_FAST = 3;
	public static final int MENG_SCHEDTEST = 4;
	public static final int MARKO_SCHEDTEST = 5;
	
	public static final double AK_MAX_BOUND = 100000*1 / TIME_PRECISION; // This is estimated according to Ak_max equation. We let denominator greater than 0.1. Becauset this is the time precision we used.
	public static final int InterfaceInfeasible = -1;
	
	public static final int TASK = 1;
	public static final int VCPU = 2;
	
	public static final int JAEWOO_IMPL = 1;
	public static final int MENG_IMPL = 2;
	public static final int IMPL_METHOD = MENG_IMPL; //Implementation method
	
	public static final int MAX_NUMCORES_TO_CHECK_MULTIPLIER = 10;
	public static final int MAX_NUMCORES_TO_CHECK_MULTIPLIER_FOR_BWSAVING = 1; //when count the average BW saving of one approach to the other, use this value.
	
	@Override
	public String toString() {
		return "GlobalVariable [TIME_PRECISION=" + TIME_PRECISION + "]";
	}
	
}
