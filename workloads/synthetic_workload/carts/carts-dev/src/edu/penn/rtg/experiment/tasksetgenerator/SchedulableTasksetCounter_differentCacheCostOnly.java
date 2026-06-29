package edu.penn.rtg.experiment.tasksetgenerator;

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.File;
import java.io.FileReader;
import java.io.FileWriter;
import java.text.DecimalFormat;
import java.util.HashMap;
import java.util.Vector;
//import java.nio.file.Files;
//import java.nio.file.Paths;

import edu.penn.rtg.common.Tool;

/**
 * Class SchedulableTasksetCounter
 * This class is to count the interface's paramter of the calculated schedulable system. 
 * It can parse all xml file to get the top component's interface and uses this to get the average bandwdith v.s. taskset utilization, 
 * each taskset's utilization v.s. taskset index, e.g., 0.10-0
 * 
 * @version 1.0
 * @author Meng Xu
 * @since 4/19/2013
 *
 */
public class SchedulableTasksetCounter_differentCacheCostOnly {
	public static final int[] whichApproaches = {GlobalVariable.MPR2, GlobalVariable.MPR2_Meng, GlobalVariable.MPR2hEDF,
		GlobalVariable.CAMPR2hEDF_TASK_CENTRIC, GlobalVariable.CAMPR2hEDF_TASK_CENTRIC_UB,
		GlobalVariable.CAMPR2hEDF_MODEL_CENTRIC, GlobalVariable.CAMPR2hEDF_COMBINED, GlobalVariable.CAMPR2hEDF_COMBINED_UB,
		GlobalVariable.CAMPR2hEDF_TASK_CENTRIC_USEMAXOH, GlobalVariable.CAMPR2hEDF_TASK_CENTRIC_UB_USEMAXOH, 
		GlobalVariable.CAMPR2hEDF_MODEL_CENTRIC_USEMAXOH, GlobalVariable.CAMPR2hEDF_COMBINED_USEMAXOH, GlobalVariable.CAMPR2hEDF_COMBINED_UB_USEMAXOH};

//	private double tasksetUtil_min;
//	private double tasksetUtil_step;
//	private double tasksetUtil_max; //include
	Vector<Vector<MPRInterface>> mPRInterfaces;
	Vector<Vector<Double>> numberOfTasksVector;
	int whichApproach;
	String rootPath;

	/**
	 * @param args
	 */
	public static void main(String[] args) {
		// TODO Auto-generated method stub
		if(args.length < 2){
			SchedulableTasksetCounter_differentCacheCostOnly.printUsage();
			System.exit(0);
		}
		
		String rootPath = ".";
		if(args[0].length() > 0){
			rootPath = args[0];
			if (!new File(rootPath).exists()) {
			    System.err.println(rootPath + " does not exist. check if the folder exist! exit");
			    System.exit(1);
			}
		}
		double tasksetUtil_min = Double.parseDouble(args[1]);
		double tasksetUtil_step = Double.parseDouble(args[2]);
		double tasksetUtil_max = Double.parseDouble(args[3]);
		int tasksetNum_perUtil = Integer.parseInt(args[4]);
		int physicalCoreNum = 5; // 5 physical cores by default
		if(args.length >= 6){
			 physicalCoreNum = Integer.parseInt(args[5]);
		}
		
		System.out.println("Input params: tasksetUtil (" + tasksetUtil_min + "," 
					+ tasksetUtil_step + ", " + tasksetUtil_max +") tasksetNum_perUtil" + tasksetNum_perUtil + "\r\n");
//		SchedulableTasksetCounter_differentCacheCostOnly.countAverageBandwidth(rootPath, tasksetUtil_min, tasksetUtil_step,
//				tasksetUtil_max, tasksetNum_perUtil);
		SchedulableTasksetCounter_differentCacheCostOnly.countEachTaskBandwidth(rootPath, tasksetUtil_min, tasksetUtil_step,
				tasksetUtil_max, tasksetNum_perUtil);
//		SchedulableTasksetCounter_differentCacheCostOnly.countSchedulableTasksetRatio(rootPath, tasksetUtil_min, tasksetUtil_step, tasksetUtil_max, tasksetNum_perUtil, physicalCoreNum);
//		SchedulableTasksetCounter_differentCacheCostOnly.countAverageBandwidthSaving(rootPath, tasksetUtil_min, tasksetUtil_step, tasksetUtil_max, tasksetNum_perUtil);
//		SchedulableTasksetCounter_differentCacheCostOnly.countEachTasksetBandwidthSaving(rootPath, tasksetUtil_min, tasksetUtil_step, tasksetUtil_max, tasksetNum_perUtil);
	}
	
	private static void printUsage(){
		String str = "========================================\r\n";
		str += "SchedulableTasksetCounter tasksetUtil(min, step, max) tasksetNum_perUtil \r\n"; 
		str += "=========================================";
		System.out.println(str);
	}
	
	public static void countEachTasksetBandwidthSaving(String rootPath, double tasksetUtil_min, double tasksetUtil_step,double tasksetUtil_max,int tasksetNum_perUtil){
		DecimalFormat df = new DecimalFormat("#.##");
		df.setMinimumFractionDigits(2);
		df.setMaximumFractionDigits(2);
		int[] groupsBandwidthSaving = {GlobalVariable.COMBINED_VS_TASKCENTRIC,
				GlobalVariable.COMBINED_UB_VS_TASKCENTRIC_UB, 
				GlobalVariable.COMBINED_UB_VS_TASKCENTRIC,
				GlobalVariable.MPR2_Meng_VS_MPR2,
				GlobalVariable.DMPR_VS_MPR2_Meng};	
		
		int[] bwSaveOrLost = {GlobalVariable.BW_SAVE, GlobalVariable.BW_LOST};
		
		for(int bwSaveOrLostIndex = 0; bwSaveOrLostIndex < bwSaveOrLost.length; bwSaveOrLostIndex++){ /*choose between bandwidth save or lost*/
			String bandwidthSaveLostStr = "";
			if(bwSaveOrLost[bwSaveOrLostIndex] == GlobalVariable.BW_SAVE){
				bandwidthSaveLostStr = "BandwidthSaveEach";
			}else if(bwSaveOrLost[bwSaveOrLostIndex] == GlobalVariable.BW_LOST){
				bandwidthSaveLostStr = "BandwidthLostEach";
			}else{
				System.err.println("ERROR: only handle bandwidth save or bandwidth lost file");
			}
			
			for(int i=0; i<groupsBandwidthSaving.length; i++){
				String outputFilename = rootPath + "/" + df.format(tasksetUtil_min) + "-" + df.format(tasksetUtil_step) + "-" 
						+df.format(tasksetUtil_max) + "-" + tasksetNum_perUtil + "/" 
						+ df.format(tasksetUtil_min) + "-" + df.format(tasksetUtil_step) + "-" 
						+df.format(tasksetUtil_max) + "-" + tasksetNum_perUtil + "-"; 
				
				SchedulableTasksetCounter_differentCacheCostOnly counter_TASKCENTRIC = null; //baseline
				SchedulableTasksetCounter_differentCacheCostOnly counter_COMBINED = null; // our proposed approach to compare
				if(groupsBandwidthSaving[i] == GlobalVariable.COMBINED_VS_TASKCENTRIC){
					counter_TASKCENTRIC = new SchedulableTasksetCounter_differentCacheCostOnly(rootPath, GlobalVariable.CAMPR2hEDF_TASK_CENTRIC);
					counter_COMBINED = new SchedulableTasksetCounter_differentCacheCostOnly(rootPath, GlobalVariable.CAMPR2hEDF_COMBINED);
					outputFilename += bandwidthSaveLostStr+ "-COMBINED-vs-TASKCENTRIC.stat";
				}else if(groupsBandwidthSaving[i] == GlobalVariable.COMBINED_UB_VS_TASKCENTRIC_UB){
					counter_TASKCENTRIC = new SchedulableTasksetCounter_differentCacheCostOnly(rootPath, GlobalVariable.CAMPR2hEDF_TASK_CENTRIC_UB);
					counter_COMBINED = new SchedulableTasksetCounter_differentCacheCostOnly(rootPath, GlobalVariable.CAMPR2hEDF_COMBINED_UB);
					outputFilename += bandwidthSaveLostStr + "-COMBINED_UB-vs-TASKCENTRIC_UB.stat";
				}else if(groupsBandwidthSaving[i] == GlobalVariable.COMBINED_UB_VS_TASKCENTRIC){
					counter_TASKCENTRIC = new SchedulableTasksetCounter_differentCacheCostOnly(rootPath, GlobalVariable.CAMPR2hEDF_TASK_CENTRIC);
					counter_COMBINED = new SchedulableTasksetCounter_differentCacheCostOnly(rootPath, GlobalVariable.CAMPR2hEDF_COMBINED_UB);
					outputFilename += bandwidthSaveLostStr + "-COMBINED_UB-vs-TASKCENTRIC.stat";
				}else if(groupsBandwidthSaving[i] == GlobalVariable.TASKCENTRIC_UB_VS_TASKCENTRIC){
					counter_TASKCENTRIC = new SchedulableTasksetCounter_differentCacheCostOnly(rootPath, GlobalVariable.CAMPR2hEDF_TASK_CENTRIC);
					counter_COMBINED = new SchedulableTasksetCounter_differentCacheCostOnly(rootPath, GlobalVariable.CAMPR2hEDF_TASK_CENTRIC_UB);
					outputFilename += bandwidthSaveLostStr + "-TASKCENTRIC_UB-vs-TASKCENTRIC.stat";
				}else if(groupsBandwidthSaving[i] == GlobalVariable.MPR2_Meng_VS_MPR2){
					counter_TASKCENTRIC = new SchedulableTasksetCounter_differentCacheCostOnly(rootPath, GlobalVariable.MPR2);
					counter_COMBINED = new SchedulableTasksetCounter_differentCacheCostOnly(rootPath,GlobalVariable.MPR2_Meng);
					outputFilename += bandwidthSaveLostStr + "-MPR2_Meng-vs-MPR2.stat";
				}else if(groupsBandwidthSaving[i] == GlobalVariable.DMPR_VS_MPR2_Meng){
					counter_TASKCENTRIC = new SchedulableTasksetCounter_differentCacheCostOnly(rootPath, GlobalVariable.MPR2_Meng);
					counter_COMBINED = new SchedulableTasksetCounter_differentCacheCostOnly(rootPath,GlobalVariable.MPR2hEDF);
					outputFilename += bandwidthSaveLostStr + "-DMPR-vs-MPR2_Meng.stat";
				}else{
					System.err.println("ERROR: Now can only compare COMBINED_VS_TASKCENTRIC, COMBINED_UB_VS_TASKCENTRIC_UB and DMPR_VS_MPR2_Meng, MPR2_Meng_VS_MPR2");
				}
				
				counter_TASKCENTRIC.parseInterfaces(tasksetUtil_min,tasksetUtil_step,tasksetUtil_max,tasksetNum_perUtil);
				counter_COMBINED.parseInterfaces(tasksetUtil_min,tasksetUtil_step,tasksetUtil_max,tasksetNum_perUtil);
				Vector<Vector<MPRInterface>> interfaces_TASKCENTRIC =  counter_TASKCENTRIC.getmPRInterfaces();
				Vector<Vector<Double>> numberOfTasksVector_TASKCENTRIC = counter_TASKCENTRIC.getNumberOfTasksVector();
 				Vector<Vector<MPRInterface>> interfaces_COMBINED =  counter_COMBINED.getmPRInterfaces();
 				Vector<Vector<Double>> numberOfTasksVector_COMBINED = counter_COMBINED.getNumberOfTasksVector();

				try{
					BufferedWriter outputFile = new BufferedWriter(new FileWriter(outputFilename));
					String str = "#util\t" + "bwSaveEach\t" + "\r\n";

					//Vector<Double> bandwidthSavingEachUtil = new Vector<Double>(interfaces_COMBINED.size());
					int arrayUtilIndex = 0;
					for(double util = tasksetUtil_min; util<tasksetUtil_max; util += tasksetUtil_step){
						for(int index = 0; index<tasksetNum_perUtil; index++){
							MPRInterface interface_TASKCENTRIC = interfaces_TASKCENTRIC.get(arrayUtilIndex).get(index);
							Double numberOfTasks_TASKCENTRIC = numberOfTasksVector_TASKCENTRIC.get(arrayUtilIndex).get(index);
							MPRInterface interface_COMBINED = interfaces_COMBINED.get(arrayUtilIndex).get(index);
							Double numberOfTasks_COMBINED = numberOfTasksVector_COMBINED.get(arrayUtilIndex).get(index);
							double bandwidth_TASKCENTRIC = -1;
							double bandwidth_COMBINED = -1;
							if(interface_TASKCENTRIC.getM_prime() > 0 && interface_TASKCENTRIC.getPi() > 0 
									&& interface_TASKCENTRIC.getTheta() > 0){
								bandwidth_TASKCENTRIC = interface_TASKCENTRIC.getTheta() * 1.0 / interface_TASKCENTRIC.getPi();
							}else if(interface_TASKCENTRIC.getM_prime() == 0){
								bandwidth_TASKCENTRIC = numberOfTasks_TASKCENTRIC * edu.penn.rtg.common.GlobalVariable.MAX_NUMCORES_TO_CHECK_MULTIPLIER_FOR_BWSAVING;
							}
							if(interface_COMBINED.getM_prime() > 0 && interface_COMBINED.getPi() > 0 
									&& interface_COMBINED.getTheta() > 0){
								bandwidth_COMBINED = interface_COMBINED.getTheta() * 1.0/ interface_COMBINED.getPi();
							}else if(interface_COMBINED.getM_prime()  == 0 ){
								bandwidth_COMBINED = numberOfTasks_COMBINED * edu.penn.rtg.common.GlobalVariable.MAX_NUMCORES_TO_CHECK_MULTIPLIER_FOR_BWSAVING;
							}
							if(bwSaveOrLost[bwSaveOrLostIndex] == GlobalVariable.BW_SAVE && 
									bandwidth_TASKCENTRIC != -1 && bandwidth_COMBINED != -1){
								if(bandwidth_COMBINED <= bandwidth_TASKCENTRIC){
									str += df.format(util) + "\t" + df.format(index)+"\t" + (bandwidth_TASKCENTRIC-bandwidth_COMBINED)+ "\r\n";
								}
							/*	else{ //when taskcentric bandwidth is invalid, all bandwidth calculated by combied is saved resource 
									if(interface_TASKCENTRIC.getM_prime() == 0 && interface_TASKCENTRIC.getTheta() > 0
											&& interface_COMBINED.getM_prime() >0 && bandwidth_COMBINED > 0){
										str += df.format(util) + "\t" + df.format(index)+"\t" + bandwidth_COMBINED + "\r\n";
									}
								}*/
							}else if(bwSaveOrLost[bwSaveOrLostIndex] == GlobalVariable.BW_LOST &&
									bandwidth_TASKCENTRIC != -1 && bandwidth_COMBINED != -1){
								if(bandwidth_COMBINED > bandwidth_TASKCENTRIC){
									str += df.format(util) + "\t" + df.format(index)+"\t" + (bandwidth_TASKCENTRIC-bandwidth_COMBINED)+ "\r\n";
								}
							/*	else if(bandwidth_COMBINED < bandwidth_TASKCENTRIC){ //when combined interface is invalid, all bandwidth calculated by taskcentric is saved resource
									if(interface_COMBINED.getM_prime() == 0 && interface_COMBINED.getTheta() > 0
											&& interface_TASKCENTRIC.getM_prime() >0 && bandwidth_TASKCENTRIC > 0){
										str += df.format(util) + "\t" + df.format(index)+"\t" + bandwidth_TASKCENTRIC + "\r\n";
									}
								}else{ //bandwidth_COMBINED == bandwidth_TASKCENTRIC
									str += df.format(util) + "\t" + df.format(index)+"\t" + df.format(0.00) + "\r\n";
								}*/
							}
						}
						arrayUtilIndex++;
					}
					outputFile.write(str);
					outputFile.close();
					if(groupsBandwidthSaving[i] == GlobalVariable.COMBINED_VS_TASKCENTRIC){
						System.out.println("==========Each Bandwdith Save/LOST (COMBINED v.s. TASKCENTRIC)================");
					}else if(groupsBandwidthSaving[i] == GlobalVariable.COMBINED_UB_VS_TASKCENTRIC_UB){
						System.out.println("==========Each Bandwdith Save/LOST (COMBINED_UB v.s. TASKCENTRIC_UB)================");
					}else if(groupsBandwidthSaving[i] == GlobalVariable.COMBINED_UB_VS_TASKCENTRIC){
						System.out.println("==========Each Bandwdith Save/LOST (COMBINED_UB v.s. TASKCENTRIC)================");
					}else if(groupsBandwidthSaving[i] == GlobalVariable.TASKCENTRIC_UB_VS_TASKCENTRIC){
						System.out.println("==========Each Bandwdith Save/LOST (TASKCENTRIC_UB v.s. TASKCENTRIC)================");
					}else if(groupsBandwidthSaving[i] == GlobalVariable.MPR2_Meng_VS_MPR2){
						System.out.println("==========Each Bandwdith Save (MPR2_Meng_VS_MPR2)================");
					}else if(groupsBandwidthSaving[i] == GlobalVariable.DMPR_VS_MPR2_Meng){
						System.out.println("==========Each Bandwdith Save (DMPR_VS_MPR2_Meng)================");
					}
					System.out.println(str);

				}catch (Exception e){
					System.err.println("Open file" + outputFilename + " fails");
				}
			}
		}
		
	}
	
	/*
	 * Count the total bandwidth saving per utilization
	 * This function should be depreciated because it can be incorporated into countAverageBandwdithSaving() and
	 * print out as the third column.
	 * */
	public static void countAverageBandwidthSaving(String rootPath, double tasksetUtil_min,double tasksetUtil_step,
			double tasksetUtil_max, int tasksetNum_perUtil){
		DecimalFormat df = new DecimalFormat("#.##");
		df.setMinimumFractionDigits(2);
		df.setMaximumFractionDigits(2);
		//bandwidth saving: Overhead aware Combined vs. Task Centric; Overhead free DMPR vs. MPR 
		int[] groupsBandwidthSaving = {GlobalVariable.COMBINED_VS_TASKCENTRIC,
				GlobalVariable.COMBINED_UB_VS_TASKCENTRIC_UB,
				GlobalVariable.COMBINED_UB_VS_TASKCENTRIC,
				GlobalVariable.TASKCENTRIC_UB_VS_TASKCENTRIC, 
				GlobalVariable.MPR2_Meng_VS_MPR2,
				GlobalVariable.DMPR_VS_MPR2_Meng};
		int[] bwSaveOrLost = {GlobalVariable.BW_SAVE, GlobalVariable.BW_LOST};
		
		for(int bwSaveOrLostIndex = 0; bwSaveOrLostIndex < bwSaveOrLost.length; bwSaveOrLostIndex++){ /*choose between bandwidth save or lost*/
			String bandwidthSaveLostStr = "";
			if(bwSaveOrLost[bwSaveOrLostIndex] == GlobalVariable.BW_SAVE){
				bandwidthSaveLostStr = "BandwidthSaveAverage";
			}else if(bwSaveOrLost[bwSaveOrLostIndex] == GlobalVariable.BW_LOST){
				bandwidthSaveLostStr = "BandwidthLostAverage";
			}else{
				System.err.println("ERROR: only handle bandwidth save or bandwidth lost file");
			}
			
			for(int i=0; i<groupsBandwidthSaving.length; i++){
				String outputFilename = rootPath + "/" + df.format(tasksetUtil_min) + "-" + df.format(tasksetUtil_step) + "-" 
						+df.format(tasksetUtil_max) + "-" + tasksetNum_perUtil + "/" 
						+ df.format(tasksetUtil_min) + "-" + df.format(tasksetUtil_step) + "-" 
						+df.format(tasksetUtil_max) + "-" + tasksetNum_perUtil + "-"; 
				
				SchedulableTasksetCounter_differentCacheCostOnly counter_TASKCENTRIC = null; //BASELINE APPROACH
				SchedulableTasksetCounter_differentCacheCostOnly counter_COMBINED = null; // OUR PROPOSED APPROACH TO COMPARE
				
				if(groupsBandwidthSaving[i] == GlobalVariable.COMBINED_VS_TASKCENTRIC){
					counter_TASKCENTRIC = new SchedulableTasksetCounter_differentCacheCostOnly(rootPath, GlobalVariable.CAMPR2hEDF_TASK_CENTRIC);
					counter_COMBINED = new SchedulableTasksetCounter_differentCacheCostOnly(rootPath, GlobalVariable.CAMPR2hEDF_COMBINED);
					outputFilename += bandwidthSaveLostStr + "-COMBINED-vs-TASKCENTRIC.stat";
				}else if(groupsBandwidthSaving[i] == GlobalVariable.COMBINED_UB_VS_TASKCENTRIC_UB){
					counter_TASKCENTRIC = new SchedulableTasksetCounter_differentCacheCostOnly(rootPath, GlobalVariable.CAMPR2hEDF_TASK_CENTRIC_UB);
					counter_COMBINED = new SchedulableTasksetCounter_differentCacheCostOnly(rootPath, GlobalVariable.CAMPR2hEDF_COMBINED_UB);
					outputFilename += bandwidthSaveLostStr + "-COMBINED_UB-vs-TASKCENTRIC_UB.stat";
				}else if(groupsBandwidthSaving[i] == GlobalVariable.COMBINED_UB_VS_TASKCENTRIC){
					counter_TASKCENTRIC = new SchedulableTasksetCounter_differentCacheCostOnly(rootPath, GlobalVariable.CAMPR2hEDF_TASK_CENTRIC);
					counter_COMBINED = new SchedulableTasksetCounter_differentCacheCostOnly(rootPath, GlobalVariable.CAMPR2hEDF_COMBINED_UB);
					outputFilename += bandwidthSaveLostStr + "-COMBINED_UB-vs-TASKCENTRIC.stat";
				}else if(groupsBandwidthSaving[i] == GlobalVariable.TASKCENTRIC_UB_VS_TASKCENTRIC){
					counter_TASKCENTRIC = new SchedulableTasksetCounter_differentCacheCostOnly(rootPath, GlobalVariable.CAMPR2hEDF_TASK_CENTRIC);
					counter_COMBINED = new SchedulableTasksetCounter_differentCacheCostOnly(rootPath, GlobalVariable.CAMPR2hEDF_TASK_CENTRIC_UB);
					outputFilename += bandwidthSaveLostStr + "-TASKCENTRIC_UB-vs-TASKCENTRIC.stat";
				}else if(groupsBandwidthSaving[i] == GlobalVariable.MPR2_Meng_VS_MPR2){
					counter_TASKCENTRIC = new SchedulableTasksetCounter_differentCacheCostOnly(rootPath, GlobalVariable.MPR2);
					counter_COMBINED = new SchedulableTasksetCounter_differentCacheCostOnly(rootPath, GlobalVariable.MPR2_Meng);
					outputFilename += bandwidthSaveLostStr + "-MPR2_Meng-vs-MPR2.stat";
				}else if(groupsBandwidthSaving[i] == GlobalVariable.DMPR_VS_MPR2_Meng){
					counter_TASKCENTRIC = new SchedulableTasksetCounter_differentCacheCostOnly(rootPath, GlobalVariable.MPR2_Meng);
					counter_COMBINED = new SchedulableTasksetCounter_differentCacheCostOnly(rootPath, GlobalVariable.MPR2hEDF);
					outputFilename += bandwidthSaveLostStr + "-DMPR-vs-MPR2_Meng.stat";
				}else{
					System.err.println("ERROR: countAverageBandwidthSaving(). No such comparison");
				}
				 
				counter_TASKCENTRIC.parseInterfaces(tasksetUtil_min,tasksetUtil_step,tasksetUtil_max,tasksetNum_perUtil);
				counter_COMBINED.parseInterfaces(tasksetUtil_min,tasksetUtil_step,tasksetUtil_max,tasksetNum_perUtil);
				Vector<Vector<MPRInterface>> interfaces_TASKCENTRIC =  counter_TASKCENTRIC.getmPRInterfaces();
				Vector<Vector<Double>> numberOfTasksVector_TASKCENTRIC = counter_TASKCENTRIC.getNumberOfTasksVector();
				Vector<Vector<MPRInterface>> interfaces_COMBINED =  counter_COMBINED.getmPRInterfaces();
				Vector<Vector<Double>> numberOfTasksVector_COMBINED = counter_COMBINED.getNumberOfTasksVector();
				
				try{
					BufferedWriter outputFile = new BufferedWriter(new FileWriter(outputFilename));

					String str = "#util\t" + "averageBWSaving\t" + "totalBWSaving\r\n";

					double numTasksetBandwidthSave = 0;
					double bandwidthTotalSave = 0;
					//Vector<Double> bandwidthSavingEachUtil = new Vector<Double>(interfaces_COMBINED.size());
					int arrayUtilIndex = 0;
					for(double util = tasksetUtil_min; util<tasksetUtil_max; util += tasksetUtil_step){
						double bandwidthTotalSavePerUtil = 0;
						double numTasksetBandwidthSavePerUtil = 0;
						for(int index = 0; index<tasksetNum_perUtil; index++){
							MPRInterface interface_TASKCENTRIC = interfaces_TASKCENTRIC.get(arrayUtilIndex).get(index);
							Double numberOfTasks_TASKCENTRIC = numberOfTasksVector_TASKCENTRIC.get(arrayUtilIndex).get(index);
							MPRInterface interface_COMBINED = interfaces_COMBINED.get(arrayUtilIndex).get(index);
							Double numberOfTasks_COMBINED = numberOfTasksVector_COMBINED.get(arrayUtilIndex).get(index);
							double bandwidth_TASKCENTRIC = -1;
							double bandwidth_COMBINED = -1;
							if(interface_TASKCENTRIC.getM_prime() > 0 && interface_TASKCENTRIC.getPi() > 0 
									&& interface_TASKCENTRIC.getTheta() > 0){
								bandwidth_TASKCENTRIC = interface_TASKCENTRIC.getTheta() * 1.0 / interface_TASKCENTRIC.getPi();
							}else if(interface_TASKCENTRIC.getM_prime() == 0){ // no valid interface, then use the upper bound num of cores in CSA
								//bandwidth_TASKCENTRIC = numberOfTasks_TASKCENTRIC * edu.penn.rtg.common.GlobalVariable.MAX_NUMCORES_TO_CHECK_MULTIPLIER_FOR_BWSAVING;
								bandwidth_TASKCENTRIC = -1;
							}
							if(interface_COMBINED.getM_prime() > 0 && interface_COMBINED.getPi() > 0 
									&& interface_COMBINED.getTheta() > 0){
								bandwidth_COMBINED = interface_COMBINED.getTheta() * 1.0/ interface_COMBINED.getPi();
							}else if(interface_COMBINED.getM_prime() == 0){
								//bandwidth_COMBINED = numberOfTasks_COMBINED * edu.penn.rtg.common.GlobalVariable.MAX_NUMCORES_TO_CHECK_MULTIPLIER_FOR_BWSAVING;
								bandwidth_COMBINED = -1;
							}
							if(bwSaveOrLost[bwSaveOrLostIndex] == GlobalVariable.BW_SAVE &&
									bandwidth_TASKCENTRIC != -1 && bandwidth_COMBINED != -1){
								if(bandwidth_COMBINED < bandwidth_TASKCENTRIC){/*when Combined approach is better*/
									bandwidthTotalSavePerUtil += bandwidth_TASKCENTRIC - bandwidth_COMBINED;
									numTasksetBandwidthSavePerUtil++;
									bandwidthTotalSave += bandwidthTotalSavePerUtil;
									numTasksetBandwidthSave++;
								}
							/*	else{
									if(interface_TASKCENTRIC.getM_prime()==0 && interface_TASKCENTRIC.getTheta()>0 
											&& interface_COMBINED.getM_prime() != 0 && bandwidth_COMBINED != 0 ){
										bandwidthTotalSavePerUtil += bandwidth_COMBINED;
										numTasksetBandwidthSavePerUtil++;
										bandwidthTotalSave += bandwidthTotalSavePerUtil;
										numTasksetBandwidthSave++;
									}
								}*/
							}else if(bwSaveOrLost[bwSaveOrLostIndex] == GlobalVariable.BW_LOST &&
									bandwidth_TASKCENTRIC != -1 && bandwidth_COMBINED != -1){
								if(bandwidth_COMBINED > bandwidth_TASKCENTRIC){/*when Combined approach is not better*/
									bandwidthTotalSavePerUtil += bandwidth_TASKCENTRIC - bandwidth_COMBINED;//it's negative
									numTasksetBandwidthSavePerUtil++;
									bandwidthTotalSave += bandwidthTotalSavePerUtil;
									numTasksetBandwidthSave++;
								}
							/*	else{
									if(interface_COMBINED.getM_prime()==0 && interface_COMBINED.getTheta()>0 
											&& interface_TASKCENTRIC.getM_prime() != 0 && bandwidth_TASKCENTRIC != 0 ){
										bandwidthTotalSavePerUtil += 0 - bandwidth_TASKCENTRIC;
										numTasksetBandwidthSavePerUtil++;
										bandwidthTotalSave += bandwidthTotalSavePerUtil;
										numTasksetBandwidthSave++;
									}
								}*/
							}
						
						}
						if(numTasksetBandwidthSavePerUtil != 0){
							//str += df.format(util) + "\t" + df.format(bandwidthTotalSavePerUtil/numTasksetBandwidthSavePerUtil) + "\r\n";
							str += df.format(util) + "\t" + df.format(bandwidthTotalSavePerUtil*1.0/numTasksetBandwidthSavePerUtil) + "\t" + df.format(bandwidthTotalSavePerUtil)+ "\r\n";
						}else{
							str += df.format(util) + "\t" + df.format(0.00) + "\t" + df.format(0.00) + "\r\n";
						}
						arrayUtilIndex++;
					}
					/*stat for all utilization: average and total bw saving/lost for all utilization*/
					if(numTasksetBandwidthSave != 0){
						str += df.format(-1) + "\t" + df.format(bandwidthTotalSave*1.0/numTasksetBandwidthSave) + "\t" + df.format(bandwidthTotalSave);
					}else{
						str += df.format(-1) + "\t" + df.format(0.00) + "\t" + df.format(0.00) ;
					}
					outputFile.write(str);
					outputFile.close();
					if(groupsBandwidthSaving[i] == GlobalVariable.COMBINED_VS_TASKCENTRIC){
						System.out.println("==========Total Bandwdith Save/Lost (COMBINED v.s. TASKCENTRIC)================");
					}else if(groupsBandwidthSaving[i] == GlobalVariable.COMBINED_UB_VS_TASKCENTRIC_UB){
						System.out.println("==========Total Bandwdith Save/Lost (COMBINED_UB v.s. TASKCENTRIC_UB)================");
					}else if(groupsBandwidthSaving[i] == GlobalVariable.COMBINED_UB_VS_TASKCENTRIC){
						System.out.println("==========Total Bandwdith Save/Lost (COMBINED_UB v.s. TASKCENTRIC)================");
					}else if(groupsBandwidthSaving[i] == GlobalVariable.TASKCENTRIC_UB_VS_TASKCENTRIC){
						System.out.println("==========Total Bandwdith Save/Lost (TASKCENTRIC_UB v.s. TASKCENTRIC)================");
					}else if(groupsBandwidthSaving[i] == GlobalVariable.MPR2_Meng_VS_MPR2){
						System.out.println("==========Total Bandwdith Save (MPR2_Meng v.s. MPR2)================");
					}else if(groupsBandwidthSaving[i] == GlobalVariable.DMPR_VS_MPR2_Meng){
						System.out.println("==========Total Bandwdith Save (DMPR v.s. MPR2_Meng)================");
					}
					System.out.println(str);

				}catch (Exception e){
					System.err.println("Open file" + outputFilename + " fails");
				}
			}
			
		}
	}
	
	/**
	 * Count the ratio of schedulable task set
	 * @param tasksetUtil_min
	 * @param tasksetUtil_step
	 * @param tasksetUtil_max
	 * @param tasksetNum_perUtil
	 * @param physicalCoreNum
	 */
	public static void countSchedulableTasksetRatio(String rootPath, double tasksetUtil_min,double tasksetUtil_step,
			double tasksetUtil_max, int tasksetNum_perUtil, int physicalCoreNum){
		
		for(int i=0; i<whichApproaches.length; i++){
			int whichApproach = whichApproaches[i];
			SchedulableTasksetCounter_differentCacheCostOnly counter = new SchedulableTasksetCounter_differentCacheCostOnly(rootPath, whichApproach);
			counter.parseInterfaces(tasksetUtil_min,tasksetUtil_step,tasksetUtil_max,tasksetNum_perUtil);
			counter.writeSchedulableTasksetRatioPerUtil(tasksetUtil_min, tasksetUtil_step, tasksetUtil_max, tasksetNum_perUtil, physicalCoreNum);
		}
		
	}
	
	
	/**
	 * Function countAverageBandwidth
	 * Count the average bandwdith for each task set utilization for each approach.
	 * Draw each line for each model: the x-axis is the taskset utilizaiton,
	 * the y-axis is the average bandwidth of the tasksets with such utilization
	 */
	public static void countAverageBandwidth(String rootPath, double tasksetUtil_min, double tasksetUtil_step,
			double tasksetUtil_max, int tasksetNum_perUtil){
		
		//When we add more calculation approach, we can just add it to the whichApproaches array, add the approch to the swtich(), and done!
		
		for(int i=0; i<whichApproaches.length; i++){
			int whichApproach = whichApproaches[i];
			SchedulableTasksetCounter_differentCacheCostOnly counter = new SchedulableTasksetCounter_differentCacheCostOnly(rootPath, whichApproach);
			counter.parseInterfaces(tasksetUtil_min,tasksetUtil_step,tasksetUtil_max,tasksetNum_perUtil);
			counter.writeAverageBandwidthPerUtil(tasksetUtil_min, tasksetUtil_step, tasksetUtil_max, tasksetNum_perUtil);
		}
		
	}
	
	/**
	 * Function countEachTaskBandwidth
	 * Count the interface's bandwidth for each task in each task set utilization.
	 * The x-axis is the taskset's index, e.g. 0.10-0
	 * The y-axis is the system's bandwidth of this taskset.
	 */
	public static void countEachTaskBandwidth(String rootPath, double tasksetUtil_min, double tasksetUtil_step,
			double tasksetUtil_max, int tasksetNum_perUtil){
		//When we add more calculation approach, we can just add it to the whichApproaches array, add the approch to the swtich(), and done!
		
		for(int i=0; i<whichApproaches.length; i++){
			int whichApproach = whichApproaches[i];
			SchedulableTasksetCounter_differentCacheCostOnly counter = new SchedulableTasksetCounter_differentCacheCostOnly(rootPath, whichApproach);
			counter.parseInterfaces(tasksetUtil_min,tasksetUtil_step,tasksetUtil_max,tasksetNum_perUtil);
			counter.writeEachTasksetBandwidth(tasksetUtil_min, tasksetUtil_step, tasksetUtil_max, tasksetNum_perUtil);
		}
	}
	
	public void writeEachTasksetBandwidth(double tasksetUtil_min,double tasksetUtil_step, double tasksetUtil_max, int tasksetNum_perUtil){
		DecimalFormat df = new DecimalFormat("#.##");
		df.setMinimumFractionDigits(2);
		df.setMaximumFractionDigits(2);
		String outputFilename = this.rootPath + "/" + df.format(tasksetUtil_min) + "-" + df.format(tasksetUtil_step) + "-" 
				+df.format(tasksetUtil_max) + "-" + tasksetNum_perUtil + "/" 
				+ df.format(tasksetUtil_min) + "-" + df.format(tasksetUtil_step) + "-" 
				+df.format(tasksetUtil_max) + "-" + tasksetNum_perUtil + "-";
		switch(this.whichApproach){
		case GlobalVariable.CAMPR2hEDF_TASK_CENTRIC: outputFilename += "CAMPR2hEDF_TASKCENTRIC-EachTasksetBandwidth.stat"; break;
		case GlobalVariable.CAMPR2hEDF_TASK_CENTRIC_UB: outputFilename += "CAMPR2hEDF_TASKCENTRIC_UB-EachTasksetBandwidth.stat"; break;
		case GlobalVariable.CAMPR2hEDF_MODEL_CENTRIC: outputFilename += "CAMPR2hEDF_MODELCENTRIC-EachTasksetBandwidth.stat"; break;
		case GlobalVariable.CAMPR2hEDF_COMBINED: outputFilename += "CAMPR2hEDF_COMBINED-EachTasksetBandwidth.stat"; break;
		case GlobalVariable.CAMPR2hEDF_COMBINED_UB: outputFilename += "CAMPR2hEDF_COMBINED_UB-EachTasksetBandwidth.stat"; break;
		case GlobalVariable.CAMPR2hEDF_TASK_CENTRIC_USEMAXOH: outputFilename += "CAMPR2hEDF_TASKCENTRIC_USEMAXOH-EachTasksetBandwidth.stat"; break;
		case GlobalVariable.CAMPR2hEDF_TASK_CENTRIC_UB_USEMAXOH: outputFilename += "CAMPR2hEDF_TASKCENTRIC_UB_USEMAXOH-EachTasksetBandwidth.stat"; break;
		case GlobalVariable.CAMPR2hEDF_MODEL_CENTRIC_USEMAXOH: outputFilename += "CAMPR2hEDF_MODELCENTRIC_USEMAXOH-EachTasksetBandwidth.stat"; break;
		case GlobalVariable.CAMPR2hEDF_COMBINED_USEMAXOH: outputFilename += "CAMPR2hEDF_COMBINED_USEMAXOH-EachTasksetBandwidth.stat"; break;
		case GlobalVariable.CAMPR2hEDF_COMBINED_UB_USEMAXOH: outputFilename += "CAMPR2hEDF_COMBINED_UB_USEMAXOH-EachTasksetBandwidth.stat"; break;
		case GlobalVariable.MPR2: outputFilename += "MPR2-EachTasksetBandwidth.stat"; break;
		case GlobalVariable.MPR2_Meng: outputFilename += "MPR2_Meng-EachTasksetBandwidth.stat"; break;
		case GlobalVariable.MPR2hEDF: outputFilename += "MPR2hEDF-EachTasksetBandwidth.stat"; break;
		default: System.err.println("SchedulableTasksetCounter: No such computation approach! exit"); System.exit(1);
		}
		
		try{
			BufferedWriter outputFile = new BufferedWriter(new FileWriter(outputFilename));
			String str = "#util\t" + "index\t" + "bw" + "\r\n";
			int arrayUtilIndex = 0;
			for(double util = tasksetUtil_min; util<tasksetUtil_max; util += tasksetUtil_step){
				for(int index = 0; index<tasksetNum_perUtil; index++){
					MPRInterface currentInterface = this.mPRInterfaces.get(arrayUtilIndex).get(index);
					if(currentInterface.getTheta() > 0 
							&& currentInterface.getTheta() <= currentInterface.getM_prime() * currentInterface.getPi()){//only count the feasible ones. Because infeasible one's bandwidth has no meaning
						//tasksetindex(0.10-0) averageBandwidth
						str += df.format(util) + "\t" + index + "\t" + df.format(currentInterface.getTheta()/currentInterface.getPi()) + "\r\n";
					}else if(currentInterface.getTheta() > 0 
							&& currentInterface.getTheta() > currentInterface.getM_prime() * currentInterface.getPi()){
						str += df.format(util) + "\t" + index + "\t" + df.format(GlobalVariable.INTERFACE_INFEASIBLE) + "\r\n";
					}else if(currentInterface.getTheta() <= 0 && currentInterface.getTheta() == GlobalVariable.FILE_NOT_EXIST){
						str += df.format(util) + "\t" + index + "\t" + df.format(GlobalVariable.INTERFACE_INFEASIBLE) + "\r\n";
						System.err.println("This interface file does not exist!");
					}else if(currentInterface.getTheta() == 0 && currentInterface.getM_prime() == 0){
						str += df.format(util) + "\t" + index + "\t" + df.format(GlobalVariable.INTERFACE_INFEASIBLE) + "\r\n";
						System.err.println("This interface's Theta = 0, taskset is empty");
					}else{
						str += df.format(util) + "\t" + index + "\t" + df.format(GlobalVariable.INTERFACE_INFEASIBLE) + "\r\n";
						System.err.println("Theta is negative and it's not because the interface file not exists. Check the input file: taskset util=" + util + "\ttaskset index=" + index + "\r\n");
						//System.exit(1);
					}
				}
				arrayUtilIndex++;
			}
			System.out.println("write averate bandwidth of each taskset utilization to the file "+outputFilename);
			System.out.println("========="+ outputFilename + "===============");
			outputFile.write(str);
			outputFile.close();
			
		}catch (Exception e){
			System.err.println("Exception in writerAverageBandwidthPerUtil: " + e.getMessage() + "\texit.");
			e.printStackTrace();
			System.exit(1);
		}
	}
	
	/**
	 * Function writeAverageBandwidthPerUtil
	 * Write the average bandwidth of a taskset utilization v.s. taskset utilization into the file.
	 * The taskset utilization is given by the function's parameter.
	 * @param tasksetUtil_min is the minimum taskset utilization
	 * @param tasksetUtil_step is the step by which the taskset utilization increases
	 * @param tasksetUtil_max is the maximum taskset utilization
	 * @param tasksetNum_perUtil is the number of tasksets for each taskset utilization
	 */
	public void writeAverageBandwidthPerUtil(double tasksetUtil_min, double tasksetUtil_step, double tasksetUtil_max, int tasksetNum_perUtil){
		DecimalFormat df = new DecimalFormat("#.##");
		df.setMinimumFractionDigits(2);
		df.setMaximumFractionDigits(2);
		String outputFilename = this.rootPath + "/" + df.format(tasksetUtil_min) + "-" + df.format(tasksetUtil_step) + "-" 
				+df.format(tasksetUtil_max) + "-" + (int)tasksetNum_perUtil + "/" 
				+ df.format(tasksetUtil_min) + "-" + df.format(tasksetUtil_step) + "-" 
				+df.format(tasksetUtil_max) + "-" + (int)tasksetNum_perUtil + "-";
		switch(this.whichApproach){
		case GlobalVariable.CAMPR2hEDF_TASK_CENTRIC: outputFilename += "CAMPR2hEDF_TASKCENTRIC-AverageBandwidth.stat"; break;
		case GlobalVariable.CAMPR2hEDF_TASK_CENTRIC_UB: outputFilename += "CAMPR2hEDF_TASKCENTRIC_UB-AverageBandwidth.stat"; break;
		case GlobalVariable.CAMPR2hEDF_MODEL_CENTRIC: outputFilename += "CAMPR2hEDF_MODELCENTRIC-AverageBandwidth.stat"; break;
		case GlobalVariable.CAMPR2hEDF_COMBINED: outputFilename += "CAMPR2hEDF_COMBINED-AverageBandwidth.stat"; break;
		case GlobalVariable.CAMPR2hEDF_COMBINED_UB: outputFilename += "CAMPR2hEDF_COMBINED_UB-AverageBandwidth.stat"; break;
		case GlobalVariable.MPR2: outputFilename += "MPR2-AverageBandwidth.stat"; break;
		case GlobalVariable.MPR2_Meng: outputFilename += "MPR2_Meng-AverageBandwidth.stat"; break;
		case GlobalVariable.MPR2hEDF: outputFilename += "MPR2hEDF-AverageBandwidth.stat"; break;
		default: System.err.println("SchedulableTasksetCounter: No such computation approach! exit"); System.exit(1);
		}
		
		try{
			BufferedWriter outputFile = new BufferedWriter(new FileWriter(outputFilename));
			String str = "#util\t" + "averageUtil\t" + "\r\n";
			int arrayUtilIndex = 0;
			for(double util = tasksetUtil_min; util<tasksetUtil_max; util += tasksetUtil_step){
				double bandwidthTotal_perUtil = 0;
				double tasksetTotal_perUtil = 0;
				for(int index = 0; index<tasksetNum_perUtil; index++){
					MPRInterface currentInterface = this.mPRInterfaces.get(arrayUtilIndex).get(index);
					if( currentInterface.getTheta() > 0 
							&& currentInterface.getTheta() <= currentInterface.getM_prime() * currentInterface.getPi()){//only count the feasible ones. Because infeasible one's bandwidth has no meaning
						bandwidthTotal_perUtil += currentInterface.getTheta() / currentInterface.getPi();
						tasksetTotal_perUtil++;
					}
				}
				//tasksetUtil averageBandwidth
				if(tasksetTotal_perUtil != 0){
					str += df.format(util) + "\t" + df.format(bandwidthTotal_perUtil/tasksetTotal_perUtil) + "\r\n";
				}
				arrayUtilIndex++;
			}
			System.out.println("write averate bandwidth of each taskset utilization to the file "+outputFilename);
			outputFile.write(str);
			System.out.println("========="+ outputFilename + "===============");
			System.out.println(str);
			outputFile.close();
			
		}catch (Exception e){
			System.err.println("Exception in writerAverageBandwidthPerUtil: " + e.getMessage() + "\texit.");
			e.printStackTrace();
			System.exit(1);
		}
	}
	
	public void writeSchedulableTasksetRatioPerUtil(double tasksetUtil_min, double tasksetUtil_step, 
			double tasksetUtil_max, double tasksetNum_perUtil, int physicalCoreNum){
		DecimalFormat df = new DecimalFormat("#.##");
		df.setMinimumFractionDigits(2);
		df.setMaximumFractionDigits(2);
		String outputFilename = rootPath + "/" + df.format(tasksetUtil_min) + "-" + df.format(tasksetUtil_step) + "-" 
				+df.format(tasksetUtil_max) + "-" + (int)tasksetNum_perUtil + "/" 
				+ df.format(tasksetUtil_min) + "-" + df.format(tasksetUtil_step) + "-" 
				+df.format(tasksetUtil_max) + "-" + (int)tasksetNum_perUtil + "-";
		switch(this.whichApproach){
		case GlobalVariable.CAMPR2hEDF_TASK_CENTRIC: outputFilename += "CAMPR2hEDF_TASKCENTRIC-SchedulableTasksetRatio.stat"; break;
		case GlobalVariable.CAMPR2hEDF_TASK_CENTRIC_UB: outputFilename += "CAMPR2hEDF_TASKCENTRIC_UB-SchedulableTasksetRatio.stat"; break;
		case GlobalVariable.CAMPR2hEDF_MODEL_CENTRIC: outputFilename += "CAMPR2hEDF_MODELCENTRIC-SchedulableTasksetRatio.stat"; break;
		case GlobalVariable.CAMPR2hEDF_COMBINED: outputFilename += "CAMPR2hEDF_COMBINED-SchedulableTasksetRatio.stat"; break;
		case GlobalVariable.CAMPR2hEDF_COMBINED_UB: outputFilename += "CAMPR2hEDF_COMBINED_UB-SchedulableTasksetRatio.stat"; break;
		case GlobalVariable.MPR2: outputFilename += "MPR2-SchedulableTasksetRatio.stat"; break;
		case GlobalVariable.MPR2_Meng: outputFilename += "MPR2_Meng-SchedulableTasksetRatio.stat"; break;
		case GlobalVariable.MPR2hEDF: outputFilename += "MPR2hEDF-SchedulableTasksetRatio.stat"; break;
		default: System.err.println("in writeSchedulableTasksetRatioPerUtil() of SchedulableTasksetCounter: No such computation approach! exit"); System.exit(1);
		}
		
		try{
			BufferedWriter outputFile = new BufferedWriter(new FileWriter(outputFilename));
			String str = "#util\t" + "schedulableRatio\t" + "\r\n";
			int arrayUtilIndex = 0;
			for(double util = tasksetUtil_min; util<tasksetUtil_max; util += tasksetUtil_step){
				double schedulableTasksetTotal_perUtil = 0;
				double tasksetTotal_perUtil = 0;
				for(int index = 0; index<tasksetNum_perUtil; index++){
					MPRInterface currentInterface = this.mPRInterfaces.get(arrayUtilIndex).get(index);
					if( currentInterface.getTheta() > 0 
							&& currentInterface.getTheta() <= currentInterface.getM_prime() * currentInterface.getPi()
							&& currentInterface.getM_prime() <= physicalCoreNum){//only count the feasible ones. Because infeasible one's bandwidth has no meaning
						schedulableTasksetTotal_perUtil++;
					}
					if(currentInterface.getTheta() != GlobalVariable.FILE_NOT_EXIST 
							&& currentInterface.getTheta() != GlobalVariable.TASKSET_EMPTY){ //handle when filter out some task set in ARVIND_SCHEDTEST
						tasksetTotal_perUtil++;
					}
					
				}
				//tasksetUtil averageBandwidth
				if(tasksetTotal_perUtil != 0){ 
					str += df.format(util) + "\t" + df.format(schedulableTasksetTotal_perUtil/tasksetTotal_perUtil) + "\r\n";
				}
				arrayUtilIndex++;
			}
			System.out.println("write schedulable taskset ratio for each taskset utilization to the file "+outputFilename);
			outputFile.write(str);
			System.out.println("========="+ outputFilename + "===============");
			System.out.println(str);
			outputFile.close();
			
		}catch (Exception e){
			System.err.println("Exception in writerAverageBandwidthPerUtil: " + e.getMessage() + "\texit.");
			e.printStackTrace();
			System.exit(1);
		}
	}
	
	/**
	 * Function parseInterface
	 * It parse each output xml file, which has the calculated interface, and get the MPR interface for each xml file.
	 * Save the interfaces into the vector as the object's property
	 */
	public void parseInterfaces(double tasksetUtil_min, double tasksetUtil_step, double tasksetUtil_max, int tasksetNum_perUtil){
		DecimalFormat df = new DecimalFormat("#.##");
		df.setMinimumFractionDigits(2);
		df.setMaximumFractionDigits(2);
		int arrayUtilIndex = 0;
		for(double util = tasksetUtil_min; util<tasksetUtil_max; util+=tasksetUtil_step){
			Vector<MPRInterface> mPRInterfaces_util = new Vector<MPRInterface>();
			Vector<Double> numberOfTasks_util = new Vector<Double>();
			for(int tasksetIndex =0; tasksetIndex < tasksetNum_perUtil; tasksetIndex++){
				String inputFilename = this.rootPath + "/" + df.format(tasksetUtil_min) + "-" + df.format(tasksetUtil_step) + "-" 
						+df.format(tasksetUtil_max) + "-" + tasksetNum_perUtil + "/" 
						+ df.format(util) + "/"
						+ tasksetIndex + "-" +  df.format(util) + "-";
				String inputTasksetFilename = this.rootPath + "/" +  df.format(tasksetUtil_min) + "-" + df.format(tasksetUtil_step) + "-" 
						+df.format(tasksetUtil_max) + "-" + tasksetNum_perUtil + "/" 
						+ df.format(util) + "/"
						+ tasksetIndex + "-" +  df.format(util) + ".txt";
				switch(this.whichApproach){
				case GlobalVariable.CAMPR2hEDF_TASK_CENTRIC: inputFilename += "CAMPR2hEDF_TASKCENTRIC-out.xml"; break;
				case GlobalVariable.CAMPR2hEDF_TASK_CENTRIC_UB: inputFilename += "CAMPR2hEDF_TASKCENTRIC_UB-out.xml"; break;
				case GlobalVariable.CAMPR2hEDF_MODEL_CENTRIC: inputFilename += "CAMPR2hEDF_MODELCENTRIC-out.xml"; break;
				case GlobalVariable.CAMPR2hEDF_COMBINED: inputFilename += "CAMPR2hEDF_COMBINED-out.xml"; break;
				case GlobalVariable.CAMPR2hEDF_COMBINED_UB: inputFilename += "CAMPR2hEDF_COMBINED_UB-out.xml"; break;
				case GlobalVariable.CAMPR2hEDF_TASK_CENTRIC_USEMAXOH: inputFilename += "CAMPR2hEDF_TASKCENTRIC_USEMAXOH-out.xml"; break;
				case GlobalVariable.CAMPR2hEDF_TASK_CENTRIC_UB_USEMAXOH: inputFilename += "CAMPR2hEDF_TASKCENTRIC_UB_USEMAXOH-out.xml"; break;
				case GlobalVariable.CAMPR2hEDF_MODEL_CENTRIC_USEMAXOH: inputFilename += "CAMPR2hEDF_MODELCENTRIC_USEMAXOH-out.xml"; break;
				case GlobalVariable.CAMPR2hEDF_COMBINED_USEMAXOH: inputFilename += "CAMPR2hEDF_COMBINED_USEMAXOH-out.xml"; break;
				case GlobalVariable.CAMPR2hEDF_COMBINED_UB_USEMAXOH: inputFilename += "CAMPR2hEDF_COMBINED_UB_USEMAXOH-out.xml"; break;
				case GlobalVariable.MPR2: inputFilename += "MPR2-out.xml"; break;
				case GlobalVariable.MPR2_Meng: inputFilename += "MPR2_Meng-out.xml"; break;
				case GlobalVariable.MPR2hEDF: inputFilename += "MPR2hEDF-out.xml"; break;
				default: System.err.println("SchedulableTasksetCounter: No such computation approach! exit"); System.exit(1);
				}
				MPRInterface mPRInterface = this.getRootComponentInterface(inputFilename);
				mPRInterfaces_util.add(mPRInterface);
				
				Double numberOfTasks = this.getNumberOfTasks(inputTasksetFilename);
				numberOfTasks_util.add(numberOfTasks);
			}
			
			if(this.mPRInterfaces == null){
				this.mPRInterfaces = new Vector<Vector<MPRInterface>>();
			}
			this.mPRInterfaces.add(mPRInterfaces_util);
			
			
			if(this.numberOfTasksVector == null){
				this.numberOfTasksVector = new Vector<Vector<Double>>();
			}
			this.numberOfTasksVector.add(numberOfTasks_util);
			
			arrayUtilIndex++;
		}
		
		if(arrayUtilIndex != this.mPRInterfaces.size()){
			System.err.println("The interfaces vector has incorrect dimension in parser. exit(1)");
			System.exit(1);
		}
		
	}
	
	/**
	 * Function SchedulableTasksetCounter
	 * Construct function
	 * @param whichApproach is defined in the GlobalVariable class in the same package
	 */
	public SchedulableTasksetCounter_differentCacheCostOnly(String rootPath, int whichApproach){
		this.whichApproach = whichApproach;
		this.mPRInterfaces = new Vector<Vector<MPRInterface>>();
		this.rootPath = rootPath;
	}

	public MPRInterface getRootComponentInterface(String inputFilename){
		try{
			File inputFile_temp = new File(inputFilename);
			if(!inputFile_temp.exists()){
				System.err.println("File " + inputFilename + " not exist.");
				return new MPRInterface(GlobalVariable.FILE_NOT_EXIST, GlobalVariable.FILE_NOT_EXIST, GlobalVariable.FILE_NOT_EXIST);
			}
			
			BufferedReader inputFile = new BufferedReader(new FileReader(inputFilename));
			String currentLine = "";
			
			
			while( (currentLine = inputFile.readLine()) != null){
				
				if(currentLine.indexOf("<model") != -1){
					String[] subStrs = currentLine.split("\"");
					int m_prime = Integer.parseInt(subStrs[1]);
					double Pi = Double.parseDouble(subStrs[3]);
					double Theta = Double.parseDouble(subStrs[5]);
					Tool.debug("m'=" + m_prime + ", Pi=" + Pi + ", Theta=" + Theta + "\r\n");
					MPRInterface mPRInterface = new MPRInterface(Pi, Theta, m_prime);
					inputFile.close();
					return mPRInterface;
					
				}
			}
			System.err.println("Parse inputfile:" + inputFilename + "Error! No top component's interface");
			inputFile.close();
			
		}catch (Exception e){
			System.err.println("isSchedulableTaskset() excetion:" + e.getMessage());
			e.printStackTrace();
			System.exit(1);
		}
		
		return  new MPRInterface(GlobalVariable.FILE_NOT_EXIST, GlobalVariable.FILE_NOT_EXIST, GlobalVariable.FILE_NOT_EXIST);
		
	}
	
	public Double getNumberOfTasks(String inputTasksetFilename){
		Double lineCounter = 0.00;
		try{
			File inputFile_temp = new File(inputTasksetFilename);
			if(!inputFile_temp.exists()){ //maybe 1) path is incorrect; 2) no task in the system, so no txt file
				//System.out.println("inputTasksetFilename=" + inputTasksetFilename);
				String inputTasksetXMLFilename = inputTasksetFilename.substring(0,inputTasksetFilename.lastIndexOf(".txt")) + "-in.xml";
				File inputXMLFile_tmp = new File(inputTasksetXMLFilename);
				if(inputXMLFile_tmp.exists()){
					return 0.0;
				}else{
					System.err.println("File " + inputTasksetFilename + " not exist. Should Not happen! exit");
					return -100.0;//work around. No use for the result in the paper
				}
			}
			
			BufferedReader inputFile = new BufferedReader(new FileReader(inputTasksetFilename));
			String currentLine = "";
	
			while( (currentLine = inputFile.readLine()) != null){
				lineCounter++;
			}
			inputFile.close();
		
		}catch (Exception e){
			System.err.println("isSchedulableTaskset() excetion:" + e.getMessage());
			e.printStackTrace();
			System.exit(1);
		}
		
		return (lineCounter-1); // first line is the comment, not task!
	}

	public Vector<Vector<MPRInterface>> getmPRInterfaces() {
		return mPRInterfaces;
	}

	public void setmPRInterfaces(Vector<Vector<MPRInterface>> mPRInterfaces) {
		this.mPRInterfaces = mPRInterfaces;
	}

	public Vector<Vector<Double>> getNumberOfTasksVector() {
		return numberOfTasksVector;
	}

	public void setNumberOfTasksVector(Vector<Vector<Double>> numberOfTasksVector) {
		this.numberOfTasksVector = numberOfTasksVector;
	}
	

	
	
	
}
